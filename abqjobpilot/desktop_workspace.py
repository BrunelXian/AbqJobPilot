"""Native single-root workspace. Display adapters never approve execution.

Classic is lazy and explicitly scoped; the product monitor has one public Reader
across all pages. Page navigation does not connect, start, stop or submit anything.
"""
import json
import re
import threading
import queue
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, font

from .execution_gui import ExecutionView, Reader
from .cockpit_display import short_identity, short_observed, progress_title
from .execution.models import ExecutionError
from .ui_resources import DisplayPreferences, LANGUAGES, translate

PAGES = ('overview','projects','queue','runs','results','agent','classic','service','settings')


def set_text(widget, value):
    """No rebuild when unchanged; preserve manual scrolling and text selection."""
    if widget.get('1.0','end-1c') == value: return
    y, x = widget.yview(), widget.xview()
    widget.configure(state='normal'); widget.delete('1.0','end'); widget.insert('1.0',value)
    widget.configure(state='disabled')
    if y: widget.yview_moveto(y[0])
    if x: widget.xview_moveto(x[0])


def json_text(value):
    return json.dumps(value, ensure_ascii=False, indent=2)


class DesktopWorkspace(ExecutionView):
    def __init__(self, app, connection=None, request_key=None, observer=None):
        self.app, self.observer = app, observer
        self.closed = False
        self.preferences = DisplayPreferences()
        self.locale = self.preferences.data['language']
        self.translated = []; self.tab_labels = []; self.heading_labels = []
        self.project = None; self.connection = connection; self.reader = None; self.readers = []
        self.product_name = None; self.connection_code = 'NOT_RUNNING'
        self.project_metadata = None
        self.last_view = None; self.last_update = '—'; self.connected = False
        self.render_rows = []
        self.run_items = {}; self.selected_run_id = None; self.next_page = None
        self.lifecycle_threads = []; self.lifecycle_results = queue.Queue()
        self.lifecycle_generation = 0; self.lifecycle_busy = False
        self.classic_pane = None; self.current_page = 'overview'; self.dialog = None
        self.identity = tk.StringVar(value=self.t('noProject'))
        self.project_label = tk.StringVar(value=self.t('noProject'))
        self.service_status = tk.StringVar(value='NOT_SELECTED')
        self.service_state = 'NOT_SELECTED'
        self.status = tk.StringVar(value=self.t('ready'))
        self.freshness = tk.StringVar(value='—')
        self.run_identity = tk.StringVar(value='Run —')
        self.resource = tk.StringVar(value=self.t('machine')+' · —')
        from .cockpit_layout import build_cockpit
        build_cockpit(self)
        self._menus();self.navigate('overview');self._recent()
        app.protocol('WM_DELETE_WINDOW',self.request_close)
        app.bind('<Control-o>',lambda _:self.choose_project());app.bind('<Control-n>',lambda _:self.new_project())
        app.bind('<F5>',lambda _:self.reconnect())
        self.timer=app.after(80,self._drain);self.resource_timer=app.after(500,self._resources)
        self.layout_timer=app.after(180,self.restore_layout)
        if connection: self.reader=Reader(connection,request_key,diagnostics=True);self.readers.append(self.reader)

    def t(self,key,**values): return translate(self.locale,key,**values)
    def bind_text(self,widget,key):
        self.translated.append((widget,key));widget.configure(text=self.t(key));return widget
    def label(self,parent,key,**kw): return self.bind_text(ttk.Label(parent,**kw),key)
    def button(self,parent,key,command): return self.bind_text(ttk.Button(parent,command=command),key)

    def tree(self,parent,columns,keys):
        holder=ttk.Frame(parent);holder.columnconfigure(0,weight=1);holder.rowconfigure(0,weight=1)
        metrics=font.Font(parent,family='Segoe UI',size=10,weight='bold')
        tree=ttk.Treeview(holder,columns=columns,show='headings',selectmode='browse',height=7)
        tree.grid(row=0,column=0,sticky='nsew')
        for col,key in zip(columns,keys):
            tree.heading(col,text=self.t(key));tree.column(col,width=170,minwidth=max(100,metrics.measure(self.t(key))+20))
            self.heading_labels.append((tree,col,key))
        y=ttk.Scrollbar(holder,orient='vertical',command=tree.yview);y.grid(row=0,column=1,sticky='ns')
        x=ttk.Scrollbar(holder,orient='horizontal',command=tree.xview);x.grid(row=1,column=0,sticky='ew')
        tree.configure(yscrollcommand=y.set,xscrollcommand=x.set)
        return holder,tree

    def text(self,parent):
        box=scrolledtext.ScrolledText(parent,state='disabled',height=8,wrap='word',font=('Segoe UI',10))
        box.pack(fill='both',expand=True);return box

    def navigate(self,key):
        if key not in self.pages:return
        self.current_page=key
        if key=='classic':
            self.current_panel.grid_remove()
            self.pages['classic'].tkraise();self.drawer.grid_remove()
            if str(self.logs) in self.pane.panes():self.pane.forget(self.logs)
        else:
            self.current_panel.grid()
            self.pages['overview'].tkraise()
            if str(self.logs) not in self.pane.panes():self.pane.add(self.logs,weight=1)
            if key in {'projects','service','runs','results','recovery','agent','settings'}:
                self.show_command({'projects':'service','results':'runs'}.get(key,key))
        self.app.configure(menu=self.classic_pane.menu_bar if key=='classic' and self.classic_pane else '')
        self._display_context()

    def show_command(self,key=None):
        # Advanced product commands must never be presented under a Classic identity.
        if self.current_page=='classic':self.navigate('overview')
        if key is None and self.drawer.winfo_ismapped():self.drawer.grid_remove();return
        key=key or 'service'
        self.drawer.grid();self.command_panels[key].tkraise()
        self.command_var.set(self.t('command.'+key))

    def select_from(self,tree):
        selected=tree.selection()
        if selected:self.select_run_id(selected[0])

    def select_run(self,event=None):
        self.select_from(self.run_tree)

    def select_run_id(self,run_id):
        if run_id not in self.run_items or run_id==self.selected_run_id:return
        self.selected_run_id=run_id
        for tree in (self.queue_tree,self.results_tree):
            if tree.exists(run_id):tree.selection_set(run_id)
        self.current_summary.set(self.t('loadingRun',run=short_identity(run_id)))
        self.log_titles['progress'].configure(text=self.t('progressUnavailable'))
        self.current_dimensions.set('—')
        for box in (*self.detail_boxes.values(),self.result_box,self.recovery_box,*self.log_widgets.values()):set_text(box,'')
        if self.reader:self.reader.select(self.run_items[run_id])

    def refresh_tables(self):
        for tree in (self.queue_tree,self.results_tree):
            query=self.filters[tree].get().casefold()
            rows=[]
            for rid,r in self.run_items.items():
                values=(r.get('job_name') or r['job_id'],r['execution']+' / '+str(r.get('execution_phase') or ''),short_identity(rid)) if tree is self.queue_tree else (r.get('job_name') or r['job_id'],r['execution'],r.get('solver_conclusion') or 'NOT_RUN',r.get('artifact_validation') or 'NOT_RUN',short_identity(rid))
                if query and query not in (' '.join(map(str,values))+' '+rid).casefold():continue
                rows.append((rid,values))
            col,reverse=self.sorting[tree]
            rows.sort(key=lambda pair:str(pair[1][col]).casefold(),reverse=reverse)
            self._update_tree(tree,rows)
            for rid,_ in rows:
                state=self.run_items[rid]['execution']
                tag='failed' if state=='FAILED' else 'unknown' if state=='UNKNOWN' else 'running' if state in {'RUNNING','START_INTENT','VALIDATING'} else ''
                tree.item(rid,tags=(tag,))
            if self.selected_run_id and tree.exists(self.selected_run_id):tree.selection_set(self.selected_run_id)

    def sort_table(self,tree,index):
        previous,reverse=self.sorting[tree]
        self.sorting[tree]=(index,not reverse if previous==index else False);self.refresh_tables()

    def legacy(self):
        self.navigate('classic')

    def _display_context(self):
        if self.current_page=='classic':
            project=self.classic_pane.project_manager.current if self.classic_pane else None
            self.project_label.set('Classic · '+project.name if project else self.t('classic'))
            self.identity.set('Classic Project '+project.project_id if project else self.t('classicSelect'))
            self.run_identity.set(self.t('classic'))
            self.page_counts.set(self.t('classicNote'))
            self.status.set(self.t('classicNote'));self.freshness.set(str(project.root) if project else self.t('legacyBlocked'))
            return
        self.project_label.set(self.product_name or self.t('noProject'))
        if self.last_view:
            ep=self.last_view['endpoint'];run=self.last_view['run']
            self.identity.set('Project '+ep['project_id']+' · '+ep['project_instance_id'])
            self.run_identity.set('Run '+(run['run_id'][:12]+'…'+run['run_id'][-8:] if run else '—'))
            self.status.set((self.t('connected') if self.connected else self.t('stale'))+' · '+self.t('dispatch')+' '+self.last_view['gate']['state']+(' · '+self.connection_code if not self.connected else ''))
        else:
            self.identity.set(('Project '+self.project_metadata['project_id']+' · '+self.project_metadata['project_instance_id']) if self.project_metadata else str(self.project) if self.project else self.t('noProject'))
            self.run_identity.set('Run —');self.status.set(self.connection_code+' · '+self.t('emptyService') if self.project else self.t('noProject'))
        self.freshness.set(self.t('observed',time=short_observed(self.last_update))+' · '+self.t('recordedSnapshot'))

    def _menus(self):
        self.project_menu.delete(0,'end')
        for key,command in (('new',self.new_project),('open',self.choose_project),('recent',lambda:self.navigate('projects')),('projectSettings',self.project_settings)):
            self.project_menu.add_command(label=self.t(key),command=command)

    def _recent(self):
        self.recent_tree.delete(*self.recent_tree.get_children())
        for i,path in enumerate(self.preferences.data.get('recent',[])[:10]):
            if isinstance(path,str):self.recent_tree.insert('','end',iid=str(i),values=(path,))

    def open_recent(self,event=None):
        selected=self.recent_tree.selection()
        if selected:self.open_path(self.recent_tree.item(selected[0],'values')[0])

    def choose_project(self):
        path=filedialog.askdirectory(parent=self.app,title=self.t('open'),mustexist=True)
        if path:self.open_path(path)

    def open_path(self,path):
        # Bounded manifest inspection distinguishes formats; discovery validates identity.
        root=Path(path)
        if (root/'project.json').is_file() and not (root/'agent_project.json').exists() and not (root/'experiment.json').exists():
            self.open_classic(path);return
        self.attach_project(path)

    def attach_project(self,path,connection=None):
        if self.reader:self.reader.stop.set()
        self.project,self.connection=str(path),connection
        self.project_metadata=None
        self.service_state='INSPECTING';self.service_status.set('INSPECTING')
        self.product_name=Path(path).name
        self.lifecycle_generation+=1;self.lifecycle_busy=False
        self.last_view=None;self.last_update='—';self.connected=False;self.selected_run_id=None;self.run_items={};self.next_page=None
        self.render_rows=[]
        self.log_titles['progress'].configure(text=self.t('progressUnavailable'))
        self.overview_split.grid_remove();self.older_button.configure(state='disabled')
        for box in self.overview_cards.values():set_text(box,'')
        for tree in (self.queue_tree,self.results_tree):tree.delete(*tree.get_children())
        self.current_summary.set(self.t("chooseRun"));self.current_dimensions.set("—");self.page_counts.set("—")
        for box in (*self.detail_boxes.values(),self.result_box,self.service_box,self.recovery_box,*self.log_widgets.values()):set_text(box,'')
        self.identity.set(self.t('notSelected'));self.project_label.set(Path(path).name);self.run_identity.set('Run —')
        self.connection_code='CONNECTING';self.status.set('CONNECTING');self.freshness.set(self.t('observed',time='—'))
        self.reader=Reader(connection,None,project=path,diagnostics=True);self.readers.append(self.reader)
        self.lifecycle_action('inspect')

    def reconnect(self):
        if not self.project:return
        previous=self.reader
        if previous:previous.stop.set()
        self.reader=Reader(self.connection,None,project=self.project,diagnostics=True)
        if self.selected_run_id in self.run_items:self.reader.select(self.run_items[self.selected_run_id])
        if previous:
            with previous.selection_lock:self.reader.page(previous.before_row)
        self.readers.append(self.reader);self._render({'connected':False,'code':'RECONNECTING'})

    def disconnect(self):
        self.lifecycle_generation+=1;self.lifecycle_busy=False
        if self.reader:self.reader.stop.set()
        self.reader=None;self.service_state='DISCONNECTED';self.service_status.set('DISCONNECTED');self._render({'connected':False,'code':'DISCONNECTED'})


    def stop_service(self):
        if self.project and messagebox.askyesno(self.t('stop'),self.t('stopConfirm'),parent=self.app):self.lifecycle_action('stop')

    def lifecycle_action(self,operation):
        super().lifecycle_action(operation)
        if self.lifecycle_busy:self.service_status.set({'inspect':'INSPECTING','start':'STARTING','stop':'STOPPING'}[operation])

    def new_project(self):
        if self.lifecycle_busy:return
        if self.dialog and self.dialog.winfo_exists():self.dialog.lift();return
        d=tk.Toplevel(self.app);self.dialog=d;d.title(self.t('new'));d.geometry('820x620');d.minsize(740,580);d.transient(self.app)
        d.columnconfigure(1,weight=1)
        name=tk.StringVar();parent=tk.StringVar();folder=tk.StringVar();stage=tk.StringVar(value=self.t('newDetail'))
        for row,key in enumerate(('projectName','location','folder','type')):
            ttk.Label(d,text=self.t(key)).grid(row=row,column=0,sticky='w',padx=12,pady=8)
        for row,var in enumerate((name,parent,folder)):ttk.Entry(d,textvariable=var).grid(row=row,column=1,sticky='ew',padx=12,pady=8)
        ttk.Button(d,text=self.t('browse'),command=lambda:parent.set(filedialog.askdirectory(parent=d,title=self.t('directoryNew')) or parent.get())).grid(row=1,column=2,padx=8)
        project_type=ttk.Combobox(d,values=('Abaqus',),state='readonly')
        project_type.current(0);project_type.grid(row=3,column=1,sticky='w',padx=12)
        for row,key in enumerate(('external','ownership','initial'),4):ttk.Label(d,text=self.t(key),wraplength=650).grid(row=row,column=0,columnspan=3,sticky='w',padx=12,pady=8)
        ttk.Label(d,textvariable=stage,wraplength=650).grid(row=7,column=0,columnspan=3,sticky='w',padx=12,pady=8)
        bar=ttk.Frame(d);bar.grid(row=8,column=0,columnspan=3,sticky='e',padx=12,pady=10)
        reviewed=[None]
        def review():
            dest=Path(parent.get())/folder.get()
            if not Path(parent.get()).is_absolute() or not folder.get() or Path(folder.get()).name!=folder.get() or folder.get() in {'.','..'} or not name.get().strip():
                stage.set(self.t('error.generic',code='INVALID_PROJECT_LOCATION'));return
            reviewed[0]=(str(dest),name.get());stage.set(str(dest)+'\n'+name.get()+' · Abaqus\n'+self.t('initial'));create.configure(state='normal')
        def commit():
            current=(str(Path(parent.get())/folder.get()),name.get())
            if reviewed[0]!=current:create.configure(state='disabled');review();return
            self.create_project(*current);d.destroy()
        ttk.Button(bar,text=self.t('review'),command=review).pack(side='left',padx=8)
        create=ttk.Button(bar,text=self.t('create'),state='disabled',command=commit);create.pack(side='left',padx=8)
        ttk.Button(bar,text=self.t('cancel'),command=d.destroy).pack(side='left')

    def create_project(self,path,name):
        if self.lifecycle_busy:return
        self.lifecycle_generation+=1;generation=self.lifecycle_generation;self.lifecycle_busy=True
        self.service_status.set('CREATING')
        def work():
            try:
                from .product_project import create_project
                create_project(path,name);result={'state':'CREATED','directory':path}
            except Exception as exc:result={'state':'BLOCKED','reason':exc.code if isinstance(exc,ExecutionError) else 'PROJECT_CREATE_FAILED'}
            self.lifecycle_results.put((generation,'create',result))
        thread=threading.Thread(target=work,name='explicit-project-create');self.lifecycle_threads.append(thread);thread.start()

    def project_settings(self):
        self.navigate('projects')
        messagebox.showinfo(self.t('projectSettings'),self.identity.get()+'\n'+str(self.project or '—')+'\n\n'+self.t('formatNote')+'\n'+self.t('ownership'),parent=self.app)

    def choose_classic(self):
        path=filedialog.askdirectory(parent=self.app,title=self.t('classicOpen'),mustexist=True)
        if path:self.open_classic(path)

    def open_classic(self,path):
        try:
            from .classic_workspace import ClassicPane
            from .project.manager import load_project_info
            project=load_project_info(path)
            if self.classic_pane:self.classic_pane.open_project(path)
            else:
                self.classic_pane=ClassicPane(self.classic_host,project,self)
                self.classic_pane.grid(row=0,column=0,sticky='nsew')
            self.classic_note.configure(text=self.t('classicNote')+' · '+project.name+'\n'+self.t('classicFallback'))
            self.preferences.remember(path);self._recent();self.navigate('classic')
        except Exception:
            messagebox.showerror(self.t('classic'),self.t('legacyBlocked'),parent=self.app)

    def change_language(self,locale):
        if locale not in LANGUAGES:return
        self.locale=locale;self.language_var.set(LANGUAGES[locale])
        self.command_selector.configure(values=[self.t('command.'+k) for k in self.command_keys])
        self.command_var.set(self.t('command.service'))
        for widget,key in self.translated:
            if widget.winfo_exists():widget.configure(text=self.t(key))
        self.inspector_selector.configure(values=[self.t(k) for k in ('identity','evidence','recovery','queue','results')])
        metrics=font.Font(self.app,family='Segoe UI',size=10,weight='bold')
        ttk.Style(self.app).configure('Cockpit.Treeview',rowheight=max(27,metrics.metrics('linespace')+8))
        for tree,col,key in self.heading_labels:
            tree.heading(col,text=self.t(key));tree.column(col,minwidth=max(170 if col=='run' else 85,metrics.measure(self.t(key))+20))
        for book,panel,key in self.tab_labels:book.tab(panel,text=self.t(key))
        self._menus()
        self.log_titles['events'].configure(text=self.t('serviceEvents'))
        self.log_titles['progress'].configure(text=self.t(progress_title((self.last_view or {}).get('progress_source'))))
        if self.classic_pane:
            self.classic_pane.lang='zh' if locale=='zh-CN' else 'en';self.classic_pane._apply_language();self.classic_pane._refresh_tables_from_cache()
        try:self.preferences.save(language=locale)
        except (OSError,ValueError):self.status.set(self.t('saveFailed'))
        if self.last_view:self._render(self.last_view,language_only=True)
        else:
            self.overview_message.set(self.t('welcomeText'))
            self.current_summary.set(self.t('chooseRun'))
            for box in self.log_widgets.values():set_text(box,self.t('noLogs'))
        self._display_context()

    def _drain(self):
        if self.closed:return
        try:value=self.reader.views.get_nowait() if self.reader else None
        except queue.Empty:value=None
        if value is not None and (not self.reader or value.get('selection_version',self.reader.selection_version)==self.reader.selection_version):self._render(value)
        try:
            generation,operation,result=self.lifecycle_results.get_nowait()
            if generation==self.lifecycle_generation:
                self.lifecycle_busy=False;self.service_state=result.get('state','BLOCKED');self.service_status.set(self.service_state+' · '+result.get('reason',''))
                if operation=='create' and result.get('state')=='CREATED':self.attach_project(result['directory']);self.navigate('overview')
                if result.get('project_name'):
                    self.product_name=result['project_name']
                    self.project_metadata={k:result[k] for k in ('project_id','project_instance_id')}
                    self.project_label.set(result['project_name']);self.identity.set('Project '+result['project_id']+' · '+result['project_instance_id'])
                    try:self.preferences.remember(self.project);self._recent()
                    except OSError:pass
                if operation=='start' and result.get('state') in {'CONNECTED','STARTING'}:self.reconnect()
                if operation=='stop' and result.get('state')=='STOPPING':self.disconnect()
                self._display_context()
        except queue.Empty:pass
        self.timer=self.app.after(80,self._drain)

    def _update_tree(self,tree,rows):
        old=set(tree.get_children()); wanted={i for i,_ in rows}
        for i in old-wanted:tree.delete(i)
        for n,(iid,values) in enumerate(rows):
            if tree.exists(iid):tree.item(iid,values=values)
            else:tree.insert('','end',iid=iid,values=values)
            tree.move(iid,'',n)

    def _render(self,value,language_only=False):
        # A queued snapshot or a locale redraw must never restore a prior selection.
        incoming=value.get('run')
        if incoming and self.selected_run_id and incoming['run_id']!=self.selected_run_id:return
        if not language_only:self.connected=value['connected']
        if not value['connected']:
            self.connection_code=value.get('code','READ_FAILED')
            self.status.set('DISCONNECTED · '+value.get('code','READ_FAILED')+' · '+self.t('stale'))
            self.freshness.set(self.t('observed',time=short_observed(self.last_update)))
            if not self.lifecycle_busy and self.service_state not in {'NOT_RUNNING','BLOCKED','STOPPING','STARTING'}:
                self.service_status.set('DISCONNECTED · '+value.get('code','READ_FAILED'))
            if not self.last_view:self.overview_message.set(self.t('emptyService') if self.project else self.t('welcomeText'))
        else:
            if not language_only:self.connection_code='CONNECTED'
            if not language_only:self.last_view=value;self.last_update=value['observed_at']
            ep,run=value['endpoint'],value['run'];page=value.get('project_page')
            self.identity.set('Project '+ep['project_id']+' · '+ep['project_instance_id'])
            self.run_identity.set('Run '+(run['run_id'][:12]+'…'+run['run_id'][-8:] if run else '—'))
            self.status.set((self.t('connected') if self.connected else self.t('stale'))+' · '+self.t('dispatch')+' '+value['gate']['state'])
            self.freshness.set(self.t('observed',time=short_observed(self.last_update))+' · '+self.t('recordedSnapshot'))
            if not self.lifecycle_busy and self.connected:
                self.service_state='CONNECTED';self.service_status.set('CONNECTED · '+ep['owner_id'])
            if page:
                self.run_items={r['run_id']:r for r in page['runs']}
                rows=[(r['run_id'],(r['run_id'],r.get('job_name') or r['job_id'],r['execution']+' / '+str(r.get('execution_phase') or ''))) for r in page['runs']]
                self.refresh_tables()
                self.page_counts.set(self.t('pageCounts',count=len(page['runs']),slot=page['slot_run_id'] or '—')+' · '+self.t('activeCount',count=sum(r['execution'] in {'START_INTENT','RUNNING','VALIDATING'} for r in page['runs'])))
                self.next_page=page['next_before_row'];self.older_button.configure(state='normal' if self.next_page is not None else 'disabled')
            if run or page and page['runs']:self.overview_split.grid()
            else:self.overview_split.grid_remove()
            self.overview_message.set(self.t('emptyProject') if page and not page['runs'] else self.t('chooseRun') if not run else (value.get('job_name') or run['job_id'])+' · '+run['execution'])
            set_text(self.overview_cards['queue'],self.t('dispatch')+': '+value['gate']['state']+'\n'+self.t('slot')+': '+str(page['slot_run_id'] if page else 'UNKNOWN')+'\n\n'+self.t('noSubmit'))
            set_text(self.service_box,self.t('owner')+'\n'+json_text({'owner_id':ep['owner_id'],'process':value.get('owner_process'),'project_id':ep['project_id'],'gate':value['gate']}))
            if run:
                diagnosis=value.get('interruption') or {};recovery=value.get('recovery') or {}
                body=diagnosis.get('body',{});projection=body.get('diagnosis',{}).get('display_projection')
                name=self.t('interruption.unknown_interrupted') if projection=='UNKNOWN_INTERRUPTED' else (projection or self.t('unavailable'))

                dimensions=[('original',run['execution']),('process',run.get('managed_completion','UNKNOWN')),('solver',run.get('solver_conclusion','NOT_RUN')),('dat',run.get('numerical_validation','NOT_RUN')),('validation',run.get('artifact_validation','NOT_RUN')),('odb',run.get('odb_content_validation','NOT_RUN')),('outside',run.get('member_completeness','UNKNOWN'))]
                self.current_summary.set((value.get('job_name') or run['job_id'])+'  ·  '+run['execution']+'  ·  '+str(run.get('execution_phase') or '')+'  ·  '+short_identity(run['run_id']))
                self.current_dimensions.set('   |   '.join(self.t(k)+': '+str(v) for k,v in dimensions[1:5])+('   |   '+name if projection=='UNKNOWN_INTERRUPTED' else ''))
                self.current_dimensions.set(self.current_dimensions.get()+'   |   '+self.t('recordedExits',count=len(run.get('process_exits') or [])))
                summary='\n'.join(self.t(k)+': '+str(v) for k,v in dimensions)
                self.render_rows=[(self.t('owner'),ep['owner_id']),('Run ID',run['run_id']),
                    (self.t('receipt'),value['receipt']['request_id'] if value['receipt'] else '—'),
                    (self.t('stage'),run['execution']),(self.t('exitVerification'),run.get('exit_verification','UNKNOWN')),
                    (self.t('validation'),run.get('artifact_validation','NOT_RUN')),
                    (self.t('process'),run.get('managed_completion','NOT_CONFIRMED'))]
                set_text(self.overview_cards['results'],summary+'\n\n'+self.t('scopeNote'))
                set_text(self.detail_boxes['identity'],summary+'\n\n'+self.t('identity')+'\n'+'\n'.join(k+': '+str(v) for k,v in self.render_rows)+'\n'+json_text({'run_id':run['run_id'],'plan_id':run['plan_id'],'backend_id':run['backend_id'],'receipt':value['receipt'],'gui_observed_at':self.last_update,'run_revision':run.get('revision'),'read_consistency':'successive bounded API reads; not an atomic Run/events snapshot'}))
                set_text(self.detail_boxes['evidence'],self.t('diagnosis')+': '+name+'\n'+self.t('notAtomic')+'\n\n'+self.t('reason')+'\n'+json_text(diagnosis if diagnosis else {'unavailable':'CAPABILITY_UNAVAILABLE'})+'\n\n'+self.t('rawEvidence')+'\n'+json_text({k:run.get(k) for k in ('managed_scope','process_exits','overall_exit','reconciliation','administrative_closeout','recovery_scope_completion')}))
                set_text(self.detail_boxes['recovery'],self.t('approvalNote')+'\n\n'+(self.t('unavailableCapability')+'\n' if recovery.get('unavailable') else '')+json_text(recovery))
                set_text(self.result_box,summary+'\n\n'+self.t('resultNote')+'\n'+json_text(value['validations']))
            else:
                self.render_rows=[(self.t('owner'),ep['owner_id']),('Run ID','—')]
                for box in (*self.detail_boxes.values(),self.result_box):set_text(box,self.t('chooseRun'))
            self.log_titles['progress'].configure(text=self.t(progress_title(value.get('progress_source'))))
            self.log_titles['events'].configure(text=self.t('serviceEvents'))
            for name in self.log_widgets:
                box=self.log_widgets[name];set_text(box,'\n'.join(json.dumps(r,ensure_ascii=False) for r in value[name]) if value[name] else self.t('noLogs'))
                if self.follow[name].get():box.see('end')
        set_text(self.recovery_box,self.detail_boxes['recovery'].get('1.0','end-1c'))
        self._display_context()
        if self.observer:
            self.observer({'connected':self.connected,'last_update':self.last_update,'status':self.status.get(),
                'run_id':self.selected_run_id,'project':self.identity.get(),'page':self.current_page,
                'run_list':[[r['run_id'],r.get('job_name') or r['job_id'],r['execution']] for r in self.run_items.values()],
                'rows':self.render_rows,'progress_text':self.log_widgets['progress'].get('1.0','end'),
                'event_text':self.log_widgets['events'].get('1.0','end'),
                'log_titles':{k:v.cget('text') for k,v in self.log_titles.items()},
                'current_summary':self.current_summary.get(),'current_dimensions':self.current_dimensions.get(),
                'results_rows':[list(self.results_tree.item(i,'values')) for i in self.results_tree.get_children()],
                'details':{k:v.get('1.0','end') for k,v in self.detail_boxes.items()}})

    def _resources(self):
        if self.closed:return
        # Reuse the existing bounded Win32 resource sampler without a Runtime.
        try:
            App=type(self.app)
            if not hasattr(self,'cpu_percent_var'):
                self.cpu_percent_var=tk.StringVar();self.memory_percent_var=tk.StringVar();self.gpu_percent_var=tk.StringVar();self._last_cpu_times=None
            self._get_system_cpu_times=lambda:App._get_system_cpu_times(self)
            cpu=App._read_cpu_percent(self)
            memory=App._read_memory_text(self)
            self.resource.set(self.t('machine')+' · CPU '+(str(cpu)+'%' if cpu is not None else '—')+' · RAM '+memory)
        except (OSError,AttributeError):self.resource.set(self.t('machine')+' · '+self.t('unavailable'))
        self.resource_timer=self.app.after(2000,self._resources)

    def _resize_text(self,event):
        width=max(260,event.width-40)
        for widget,key in self.translated:
            try:
                if widget.winfo_class()=='TLabel' and int(widget.cget('wraplength')):
                    widget.configure(wraplength=min(850,width))
            except (tk.TclError,ValueError):pass

    def restore_layout(self,default=False):
        values={} if default else self.preferences.data.get('dividers',{})
        for key,pane,fallback in (('main',self.pane,.58),('logs',self.logs,.5),('overview',self.overview_split,.5),('runs',self.run_split,.5)):
            try:
                fraction=float(values.get(key,fallback));fraction=max(.15,min(.85,fraction))
                size=pane.winfo_height() if key=='main' else pane.winfo_width()
                if size>10 and len(pane.panes())>1:pane.sashpos(0,int(size*fraction))
            except (ValueError,TypeError,tk.TclError):pass

    def show_api(self):
        messagebox.showinfo(self.t('documentation'),'abqjobpilot.service_lifecycle.ServiceLifecycleManager\ninspect / connect / start / disconnect / stop\n\nclient.inspect_interrupted_execution(run_id)\nclient.preview_interrupted_recovery(run_id)\n\n'+self.t('approvalNote'),parent=self.app)

    def request_close(self):
        if self.classic_pane and self.classic_pane.runner.is_running():
            messagebox.showwarning(self.t('classic'),self.t('activeClassic'),parent=self.app);return
        self.app.destroy()

    def close(self):
        if self.closed:return
        self.closed=True
        for reader in self.readers:reader.stop.set()
        for timer in (self.timer,self.resource_timer,self.layout_timer):
            try:self.app.after_cancel(timer)
            except tk.TclError:pass
        dividers={}
        for key,pane in (('main',self.pane),('logs',self.logs),('overview',self.overview_split),('runs',self.run_split)):
            try:
                size=pane.winfo_height() if key=='main' else pane.winfo_width()
                if size>10 and len(pane.panes())>1:dividers[key]=pane.sashpos(0)/size
            except tk.TclError:pass
        try:self.preferences.save(language=self.locale,geometry=self.app.geometry(),dividers=dividers)
        except (OSError,ValueError):pass
        if self.classic_pane:self.classic_pane.close_callbacks()
