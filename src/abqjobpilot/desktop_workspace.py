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
        configured_language = getattr(app, 'desktop_shell_settings', {}).get('language')
        self.locale = configured_language if configured_language in LANGUAGES else self.preferences.data['language']
        self.translated = []; self.tab_labels = []; self.heading_labels = []
        self.project = None; self.connection = connection; self.reader = None; self.readers = []
        self.product_name = None; self.connection_code = 'NOT_RUNNING'
        self.project_metadata = None
        self.last_view = None; self.last_update = '—'; self.connected = False
        self.render_rows = []
        self.run_items = {}; self.selected_run_id = None; self.selected_job_id = None; self.next_page = None
        self._syncing_table_selection = False
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
        self.skin_loader = getattr(app, 'skin_loader', None)
        from .cockpit_layout import build_cockpit
        build_cockpit(self)
        self.apply_typography()
        self._menus();self.navigate('overview');self.fit_toolbar_labels();self._recent()
        app.protocol('WM_DELETE_WINDOW',self.request_close)
        app.bind('<Control-o>',lambda _:self.choose_project());app.bind('<Control-n>',lambda _:self.new_project())
        app.bind('<F5>',lambda _:self.reconnect())
        recent=self.preferences.data.get('recent',[])
        if app.desktop_shell_settings.get('auto_connect_last_project') and recent and isinstance(recent[0],str):
            app.after_idle(lambda path=recent[0]:self.open_path(path))
        self.timer=app.after(80,self._drain);self.resource_timer=app.after(500,self._resources)
        self.layout_timer=app.after(180,self.restore_layout)
        if connection: self.reader=Reader(connection,request_key,diagnostics=True);self.readers.append(self.reader)
        from .environment_gui import initialize
        initialize(self)

    def detect_environments(self):
        if self.environment_busy or self.environment_manager is None:return
        self.environment_busy=True
        def scan():
            try:
                self.environment_manager.auto_detect()
                self.environment_error=""
            except (ExecutionError,OSError,ValueError) as exc:
                self.environment_error=str(exc)
            finally:
                self.environment_busy=False
        self.environment_thread=threading.Thread(target=scan,name='abaqus-static-discovery',daemon=True)
        self.environment_thread.start()

    def show_environments(self):
        from .environment_gui import EnvironmentDialog
        if self.environment_dialog and self.environment_dialog.winfo_exists():
            self.environment_dialog.lift()
        else:
            if not self.environment_busy:
                from .abaqus_environments import EnvironmentManager
                try:
                    self.environment_manager=EnvironmentManager()
                    self.environment_error=""
                except (ExecutionError,OSError,ValueError,KeyError,TypeError) as exc:
                    self.environment_manager=None
                    self.environment_error=str(exc)
            self.environment_dialog=EnvironmentDialog(self)

    def t(self,key,**values): return translate(self.locale,key,**values)

    def fit_toolbar_labels(self):
        """Use natural button widths; keep the Project selector compact."""
        # ttk's natural width follows the translated action label. Fixed English
        # character widths clipped German and French labels in the compact bar.
        self.add_task_button.configure(width=-1)
        self.start_queue_button.configure(width=-1)

    def apply_typography(self):
        """Match Stable's readable Segoe sizing with script-aware Windows fallbacks."""
        families = set(font.families(self.app))
        configured = getattr(getattr(self.app, 'desktop_skin', None), 'resources', {}).get('font_family', 'Segoe UI')
        choices = {
            'zh-CN': ('Microsoft YaHei UI', configured, 'Segoe UI'),
            'ja-JP': ('Yu Gothic UI', 'Yu Gothic', configured, 'Segoe UI'),
            'en': (configured, 'Segoe UI'), 'fr-FR': (configured, 'Segoe UI'), 'de-DE': (configured, 'Segoe UI'),
        }.get(self.locale, (configured, 'Segoe UI'))
        family = next((name for name in choices if name in families), 'TkDefaultFont')
        self.font_family = family
        self.font_size = max(10, int(getattr(getattr(self.app, 'desktop_skin', None), 'resources', {}).get('font_size', 10)))
        for name in ('TkDefaultFont', 'TkTextFont', 'TkMenuFont', 'TkHeadingFont'):
            try:
                named = font.nametofont(name, root=self.app)
                named.configure(family=family, size=self.font_size, weight='normal')
            except tk.TclError:
                pass
        sty = ttk.Style(self.app)
        sty.theme_use('clam')
        sty.configure('.', font=(family, self.font_size))
        sty.configure('TLabel', font=(family, self.font_size))
        sty.configure('Cockpit.Header.TLabel', font=(family, self.font_size, 'bold'))
        sty.configure('TButton', font=(family, self.font_size), padding=(12, 6))
        sty.configure('TMenubutton', font=(family, self.font_size), padding=(8, 4))
        sty.configure('TCombobox', font=(family, self.font_size), padding=(4, 3))
        sty.configure('Treeview', font=(family, self.font_size), rowheight=28)
        # Stable uses a normal body font and a Semibold heading family, not a
        # bold weight applied to every localized glyph.
        heading_family = next((name for name in ('Segoe UI Semibold', 'Segoe UI') if name in families), family)
        self.heading_family = heading_family
        sty.configure('Treeview.Heading', font=(heading_family, self.font_size), padding=(6, 6))
        sty.configure('Cockpit.Treeview', font=(family, self.font_size), rowheight=28)
        sty.configure('Cockpit.Treeview.Heading', font=(heading_family, self.font_size), padding=(6, 6))
        for tree, col, key in getattr(self, 'heading_labels', ()):
            metrics = font.Font(self.app, family=heading_family, size=self.font_size)
            tree.heading(col, text=self.t(key))
            tree.column(col, minwidth=max(100, metrics.measure(self.t(key)) + 24))
        for box in getattr(self, 'log_widgets', {}).values():
            box.configure(font=('Consolas', self.font_size))

    def bind_text(self,widget,key):
        self.translated.append((widget,key));widget.configure(text=self.t(key));return widget
    def label(self,parent,key,**kw): return self.bind_text(ttk.Label(parent,**kw),key)
    def button(self,parent,key,command): return self.bind_text(ttk.Button(parent,command=command),key)

    def tree(self,parent,columns,keys):
        holder=ttk.Frame(parent);holder.columnconfigure(0,weight=1);holder.rowconfigure(0,weight=1)
        metrics=font.Font(parent,family=getattr(self,'heading_family',getattr(self,'font_family','Segoe UI')),size=getattr(self,'font_size',10))
        tree=ttk.Treeview(holder,columns=columns,show='headings',selectmode='browse',height=7)
        tree.grid(row=0,column=0,sticky='nsew')
        for col,key in zip(columns,keys):
            tree.heading(col,text=self.t(key));tree.column(col,width=170,minwidth=max(100,metrics.measure(self.t(key))+20))
            self.heading_labels.append((tree,col,key))
        y=ttk.Scrollbar(holder,orient='vertical',command=tree.yview);y.grid(row=0,column=1,sticky='ns')
        x=ttk.Scrollbar(holder,orient='horizontal',command=tree.xview)
        tree.configure(yscrollcommand=y.set,xscrollcommand=x.set)
        tree.bind('<Configure>', lambda _e, t=tree, bar=x: self._sync_tree_xscroll(t, bar), add='+')
        tree.bind('<ButtonRelease-1>', lambda _e, t=tree, bar=x: self._sync_tree_xscroll(t, bar), add='+')
        tree._horizontal_scrollbar = x
        return holder,tree

    def _sync_tree_xscroll(self, tree, bar):
        try:
            required = sum(int(tree.column(col, 'width')) for col in tree['columns'])
            if required > max(1, tree.winfo_width() - 4):
                if not bar.winfo_ismapped(): bar.grid(row=1, column=0, sticky='ew')
            elif bar.winfo_ismapped():
                bar.grid_remove()
        except (tk.TclError, ValueError):
            pass

    def copy_text(self,widget):
        try:value=widget.get('sel.first','sel.last')
        except tk.TclError:return 'break'
        self.app.clipboard_clear();self.app.clipboard_append(value)
        return 'break'

    def text(self,parent):
        from .skin_system import DEFAULT_THEME
        palette=dict(DEFAULT_THEME)
        skin=getattr(self.app,'desktop_skin',None)
        if skin:palette.update(skin.theme)
        if getattr(self.app,'desktop_shell_settings',{}).get('appearance')=='dark':
            palette.update(background='#171a21',surface='#222733',foreground='#e8edf5',muted='#a5b0c0',border='#384150')
        box=scrolledtext.ScrolledText(parent,state='disabled',height=8,wrap='word',font=(skin.resources['font_family'] if skin else 'Segoe UI',skin.resources['font_size'] if skin else 10),background=palette['surface'],foreground=palette['foreground'],insertbackground=palette['foreground'],relief='flat',borderwidth=1)
        box.pack(fill='both',expand=True);return box

    def navigate(self,key):
        if key == 'classic':
            self.status.set(self.t('classicUnavailable'))
            return
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
        self.app.configure(menu=self.menu_bar)
        self._display_context()

    def show_command(self,key=None):
        # Advanced product commands must never be presented under a Classic identity.
        if self.current_page=='classic':self.navigate('overview')
        if key is None and self.drawer.winfo_ismapped():self.drawer.grid_remove();return
        key=key or 'service'
        self.drawer.grid();self.command_panels[key].tkraise()
        self.command_var.set(self.t('command.'+key))

    def open_agent_command(self):
        """Open the separate command console with a read-only command allowlist."""
        existing=getattr(self,'agent_console',None)
        if existing is not None and existing.winfo_exists():existing.lift();return
        from .command_console import AgentCommandConsole
        from .command_parser import parse_agent_command, CommandParseError
        recent=self.preferences.path.with_name('agent-command-recent.json')
        language='zh' if self.locale=='zh-CN' else 'en'
        console=AgentCommandConsole(self.app,language=language,recent_file=str(recent))
        original=console.session.execute
        allowed={'help','clear','list','status','outputs'}
        def read_only(command_text):
            try:parsed=parse_agent_command(command_text)
            except CommandParseError:return original(command_text)
            command=parsed.get('command')
            if command=='project' and parsed.get('project_action') in {'list','use','show'}:
                return original(command_text)
            if command in allowed:return original(command_text)
            return {'status':'NOT_AVAILABLE_IN_NATIVE_GUI',
                    'message':'This command is unavailable in the Native Tk interface.',
                    'data':{},'queue_changed':False,'target_changed':False}
        console.session.execute=read_only
        console.on_queue_changed=None
        self.agent_console=console

    def select_from(self,tree):
        if self._syncing_table_selection:return
        selected=tree.selection()
        if selected:self.select_job(selected[0],tree)

    def select_run(self,event=None):
        self.select_from(self.run_tree)

    def select_run_id(self,run_id):
        if run_id not in self.run_items:return
        self.selected_job_id=self.run_items[run_id].get('job_id')
        if run_id==self.selected_run_id:return
        self.selected_run_id=run_id
        self._syncing_table_selection=True
        for tree in (self.queue_tree,self.results_tree):
            if self.selected_job_id and tree.exists(self.selected_job_id):tree.selection_set(self.selected_job_id)
        # ttk emits <<TreeviewSelect>> after the current Tcl command returns.
        # Hold the guard through that event turn so Job rows with several Runs
        # do not alternate the selected terminal and latest attempt forever.
        self.app.after_idle(lambda:setattr(self,'_syncing_table_selection',False))
        self.current_summary.set(self.t('loadingRun',run=short_identity(run_id)))
        self.log_titles['progress'].configure(text=self.t('progressUnavailable'))
        self.current_dimensions.set('—')
        for box in (*self.detail_boxes.values(),self.result_box,self.recovery_box,*self.log_widgets.values()):set_text(box,'')
        if self.reader:self.reader.select(self.run_items[run_id])

    def select_job(self,job_id,tree):
        from .job_projection import project_jobs
        job=project_jobs(self.run_items).get(job_id)
        if not job:return
        run=job['latest'] if tree is self.queue_tree else (job.get('terminal') or job['latest'])
        self.selected_job_id=job_id
        self.select_run_id(run['run_id'])
        self.show_command('runs')
        self.inspector_selector.current(1);self.details.select(1)

    def refresh_tables(self):
        from .job_projection import project_jobs, queue_row, result_row
        projected=project_jobs(self.run_items)
        queue_jobs=[v for v in projected.values() if v['queue_visible']]
        queue_jobs.sort(key=lambda v:(str(v['latest'].get('created_at') or ''),v['job_id']),reverse=True)
        result_jobs=[v for v in projected.values() if v['result_visible']]
        for tree in (self.queue_tree,self.results_tree):
            query=self.filters[tree].get().casefold()
            source=queue_jobs if tree is self.queue_tree else result_jobs
            rows=[]
            for index,job in enumerate(source,1):
                iid,values=queue_row(index,job,self.t('unavailable')) if tree is self.queue_tree else result_row(job,self.t('unavailable'))
                if query and query not in (' '.join(map(str,values))+' '+iid).casefold():continue
                rows.append((iid,values))
            col,reverse=self.sorting[tree]
            if tree is self.queue_tree and col==0:
                rows.sort(key=lambda pair:int(pair[1][col]),reverse=reverse)
            else:
                rows.sort(key=lambda pair:str(pair[1][col]).casefold(),reverse=reverse)
            self._update_tree(tree,rows)
            table_key='queue' if tree is self.queue_tree else 'results'
            self.table_counts[table_key].set(str(len(rows)))
            self.app.after_idle(lambda t=tree: self._sync_tree_xscroll(t, t._horizontal_scrollbar))
            for rid,_ in rows:
                job=projected[rid]
                state=job['latest'].get('execution','UNKNOWN')
                tag='failed' if state=='FAILED' else 'unknown' if state=='UNKNOWN' else 'running' if state in {'RUNNING','START_INTENT','VALIDATING'} else ''
                tree.item(rid,tags=(tag,))
            if (self.selected_job_id and tree.exists(self.selected_job_id)
                    and tree.selection() != (self.selected_job_id,)):
                # Restoring Job highlighting must not select a different attempt.
                self._syncing_table_selection=True
                tree.selection_set(self.selected_job_id)
                self.app.after_idle(lambda:setattr(self,'_syncing_table_selection',False))

    def open_table_filter(self, table):
        tree=self.queue_tree if table=='queue' else self.results_tree
        old=self.filter_windows.get(table)
        if old is not None and old.winfo_exists():old.lift();return
        win=tk.Toplevel(self.app);win.title(self.t('filter'));win.transient(self.app);win.resizable(False,False)
        win.columnconfigure(0,weight=1)
        entry=ttk.Entry(win,textvariable=self.filters[tree],width=36);entry.grid(row=0,column=0,columnspan=3,sticky='ew',padx=9,pady=(9,5));entry.focus_set()
        ttk.Button(win,text=self.t('clear'),command=lambda:self.filters[tree].set('')).grid(row=1,column=0,padx=8,pady=8,sticky='w')
        ttk.Button(win,text=self.t('close'),command=win.destroy).grid(row=1,column=2,padx=8,pady=8,sticky='e')
        self.filter_windows[table]=win
        win.protocol('WM_DELETE_WINDOW',win.destroy)
        win.bind('<Return>',lambda _e:win.destroy())
        win.bind('<Escape>',lambda _e:win.destroy())

    def sort_table(self,tree,index):
        previous,reverse=self.sorting[tree]
        self.sorting[tree]=(index,not reverse if previous==index else False);self.refresh_tables()

    def legacy(self):
        self.status.set(self.t('classicUnavailable'))

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
            execution=run.get('execution') if run else None
            self.status.set((self.t('connected') if self.connected else self.t('stale'))+' · '+self.t('dispatch')+' '+self.last_view['gate']['state']+(' · '+str(execution) if execution else '')+(' · '+self.connection_code if not self.connected else ''))
        else:
            self.identity.set(('Project '+self.project_metadata['project_id']+' · '+self.project_metadata['project_instance_id']) if self.project_metadata else str(self.project) if self.project else self.t('noProject'))
            self.run_identity.set('Run —');self.status.set('Owner · '+self.connection_code if self.project else 'Owner · NOT_RUNNING')
        self.freshness.set(self.t('observed',time=short_observed(self.last_update))+' · '+self.t('recordedSnapshot'))

    def _menus(self):
        for menu in (self.project_menu,self.project_bar_menu):
            menu.configure(postcommand=lambda target=menu:self._fill_project_menu(target))
            self._fill_project_menu(menu)
        self.task_menu.delete(0,'end');self.task_menu.add_command(label=self.t('addTaskAction')+' TEST_ONLY',command=self.add_test_task);self.task_menu.add_command(label=self.t('startQueueAction')+' TEST_ONLY',command=self.submit_test_task)
        self.view_menu.delete(0,'end')
        for label,key in (('overview','overview'),('projects','projects'),('queue','queue'),('runs','runs'),('results','results')):self.view_menu.add_command(label=self.t(label),command=lambda page=key:self.navigate(page))
        self.tools_menu.delete(0,'end');self.tools_menu.add_command(label=self.t('reconnect')+' Owner',command=self.reconnect);self.tools_menu.add_command(label=self.t('refresh'),command=self.reconnect)
        self.agent_menu.delete(0,'end');self.agent_menu.add_command(label=self.t('agentCommand'),command=self.open_agent_command);self.agent_menu.add_command(label=self.t('agent'),command=lambda:self.navigate('agent'))
        self.help_menu.delete(0,'end');self.help_menu.add_command(label=self.t('menu.about'),command=lambda:self.show_command('settings'))
        labels=('menu.project','menu.task','menu.view','menu.tools','menu.agent','menu.help')
        self.app.configure(menu=self.menu_bar)
        for index,key in enumerate(labels):self.menu_bar.entryconfigure(index,label=self.t(key))

    def _fill_project_menu(self, menu):
        menu.delete(0,'end')
        available = not self.lifecycle_busy
        for key, command, enabled in (
                ('new',self.new_project,available),('open',self.choose_project,available),
                ('closeProject',self.close_project,available and bool(self.project)),
                ('managementProjectFolder',self.open_project_folder,bool(self.project))):
            menu.add_command(label=self.t(key),command=command,state='normal' if enabled else 'disabled')
        if not hasattr(menu,'recent_projects'):
            menu.recent_projects=tk.Menu(menu,tearoff=False,
                postcommand=lambda:self._populate_recent_projects(menu.recent_projects))
        self._populate_recent_projects(menu.recent_projects)
        menu.add_cascade(label=self.t('recent'),menu=menu.recent_projects)
        menu.add_separator()
        menu.add_command(label=self.t('exportProject'),state='disabled')
        menu.add_command(label=self.t('importProject'),state='disabled')
        menu.add_command(label=self.t('projectSettings'),command=self.project_settings)

    def _recent_project_name(self, path):
        from .service_discovery import read_document
        root=Path(path)
        try:
            manifest=read_document(root/'agent_project.json')
            name=manifest.get('display_name')
            if isinstance(name,str) and name.strip() and len(name)<=80 and all(ord(c)>=32 for c in name):
                return name.strip()
        except (ExecutionError,OSError,ValueError,TypeError):
            pass
        return root.name or str(root)

    def _populate_recent_projects(self, menu):
        menu.delete(0,'end')
        entries=[path for path in self.preferences.data.get('recent',[]) if isinstance(path,str)][:10]
        if not entries:
            menu.add_command(label=self.t('noRecent'),state='disabled')
        for path in entries:
            menu.add_command(label=f"{self._recent_project_name(path)} ({path})",
                             command=lambda target=path:self.open_path(target))

    def _recent(self):
        self.recent_tree.delete(*self.recent_tree.get_children())
        for i,path in enumerate(self.preferences.data.get('recent',[])[:10]):
            if isinstance(path,str):self.recent_tree.insert('','end',iid=str(i),values=(path,))

    def open_recent(self,event=None):
        selected=self.recent_tree.selection()
        if selected:self.open_path(self.recent_tree.item(selected[0],'values')[0])

    def choose_project(self):
        if self.lifecycle_busy:return
        path=filedialog.askdirectory(parent=self.app,title=self.t('open'),mustexist=True)
        if path:self.open_path(path)

    def open_path(self,path):
        if self.lifecycle_busy:
            self.status.set(self.t('projectNavigationBusy'));return
        from .product_project import inspect_project
        try:
            metadata=inspect_project(path)
            if metadata['kind']=='LEGACY_PROJECT':
                self.status.set(self.t('legacyBlocked'));return
            if metadata['kind'] not in ('AGENT_FIRST_PRODUCT','AGENT_FIRST_EXPERIMENT'):
                raise ExecutionError(metadata.get('reason','NOT_AN_AGENT_FIRST_PROJECT'),'Project cannot be opened')
        except (ExecutionError,OSError,ValueError) as exc:
            messagebox.showerror(self.t('open'),self.t('projectOpenError',path=str(path),
                code=getattr(exc,'code','PROJECT_UNAVAILABLE')),parent=self.app)
            return
        self.attach_project(path)
        self.product_name=metadata.get('display_name') or Path(path).name
        self.project_metadata={k:metadata[k] for k in ('project_id','project_instance_id')}
        self.project_label.set(self.product_name)
        try:self.preferences.remember(path);self._recent()
        except (OSError,ValueError):self.status.set(self.t('saveFailed'))

    def close_project(self):
        if self.lifecycle_busy or not self.project:return
        self.disconnect()
        self.project=None;self.connection=None;self.product_name=None;self.project_metadata=None
        self.last_view=None;self.last_update='—';self.connected=False
        self.selected_run_id=None;self.selected_job_id=None;self.run_items={};self.render_rows=[];self.next_page=None
        self.connection_code='NOT_RUNNING';self.service_state='NOT_SELECTED';self.service_status.set('NOT_SELECTED')
        self.older_button.configure(state='disabled')
        for tree in (self.queue_tree,self.results_tree):tree.delete(*tree.get_children())
        for box in (*self.overview_cards.values(),*self.detail_boxes.values(),
                    self.result_box,self.service_box,self.recovery_box):set_text(box,'')
        self.current_summary.set(self.t('chooseRun'));self.current_dimensions.set('—');self.page_counts.set('—')
        self.overview_message.set(self.t('welcomeText'))
        set_text(self.log_widgets['progress'],self.t('noProgress'))
        set_text(self.log_widgets['events'],self.t('noEvents'))
        self.log_titles['progress'].configure(text=self.t('progressUnavailable'))
        self._display_context()

    def open_project_folder(self):
        if self.project:
            import os
            try:os.startfile(str(Path(self.project)))
            except OSError:
                messagebox.showerror(self.t('managementProjectFolder'),
                    self.t('projectOpenError',path=self.project,code='PATH_UNAVAILABLE'),parent=self.app)

    def attach_project(self,path,connection=None):
        if self.reader:self.reader.stop.set()
        self.project,self.connection=str(path),connection
        self.project_metadata=None
        self.service_state='INSPECTING';self.service_status.set('INSPECTING')
        self.product_name=Path(path).name
        self.lifecycle_generation+=1;self.lifecycle_busy=False
        self.last_view=None;self.last_update='—';self.connected=False;self.selected_run_id=None;self.selected_job_id=None;self.run_items={};self.next_page=None
        self.render_rows=[]
        self.log_titles['progress'].configure(text=self.t('progressUnavailable'))
        self.older_button.configure(state='disabled')
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


    def start_service(self):
        if self.project and messagebox.askyesno(self.t('start'),self.t('startConfirm'),parent=self.app):
            self.lifecycle_action('start')

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

    def add_test_task(self):
        self._test_task_action('task')

    def submit_test_task(self):
        self._test_task_action('submit')

    def _test_task_action(self, action):
        if not self.project:
            messagebox.showinfo('TEST_ONLY', 'Select an Agent-first Project first.',parent=self.app);return
        if not messagebox.askyesno('TEST_ONLY',
            'Fixed simulation only. One task / one simulated Run per Project. No Abaqus.\n'
            'Start Owner/Service first. Continue?',parent=self.app):return
        try:
            from .agent_public import call
            result=call(str(self.project),action)
            messagebox.showinfo('TEST_ONLY',json_text(result),parent=self.app)
            self.reconnect()
        except Exception as exc:
            messagebox.showerror('TEST_ONLY',str(getattr(exc,'code','UNAVAILABLE'))+'\n'+str(exc)+
                '\nUse Service → Start Owner for this Project. No direct Solver fallback.',parent=self.app)

    def project_settings(self):
        self.navigate('projects')
        messagebox.showinfo(self.t('projectSettings'),self.identity.get()+'\n'+str(self.project or '—')+'\n\n'+self.t('formatNote')+'\n'+self.t('ownership'),parent=self.app)

    def choose_classic(self):
        path=filedialog.askdirectory(parent=self.app,title=self.t('classicOpen'),mustexist=True)
        if path:self.open_classic(path)

    def open_classic(self,path):
        try:
            from .application_runtime import require_classic_source
            require_classic_source()
            from .classic_workspace import ClassicPane
            from .project.manager import load_project_info
            project=load_project_info(path)
            if self.classic_pane:self.classic_pane.open_project(path)
            else:
                self.classic_pane=ClassicPane(self.classic_host,project,self)
                self.classic_pane.grid(row=0,column=0,sticky='nsew')
            self.classic_note.configure(text=self.t('classicNote')+' · '+project.name+'\n'+self.t('classicFallback'))
            self.preferences.remember(path);self._recent();self.navigate('classic')
        except Exception as exc:
            code=exc.code if isinstance(exc,ExecutionError) else 'LEGACY_PROJECT_REJECTED'
            if not hasattr(self,'status'):
                raise
            self.status.set(self.t('classicUnavailable')+' · '+code)

    def change_language(self,locale):
        if locale not in LANGUAGES:return
        self.locale=locale;self.language_var.set(LANGUAGES[locale])
        self.skin_var.set(self.t('defaultLayout'))
        self.skin_box.configure(values=(self.t('defaultLayout'),),width=max(10,len(self.t('defaultLayout'))))
        self.command_selector.configure(values=[self.t('command.'+k) for k in self.command_keys])
        self.command_var.set(self.t('command.service'))
        for widget,key in self.translated:
            if widget.winfo_exists():widget.configure(text=self.t(key))
        self.inspector_selector.configure(values=[self.t(k) for k in ('identity','evidence','recovery','queue','results')])
        self.apply_typography()
        metrics=font.Font(self.app,family=self.font_family,size=self.font_size,weight='bold')
        for tree,col,key in self.heading_labels:
            tree.heading(col,text=self.t(key));tree.column(col,minwidth=max(170 if col=='run' else 85,metrics.measure(self.t(key))+20))
        for book,panel,key in self.tab_labels:book.tab(panel,text=self.t(key))
        self._menus()
        if hasattr(self, 'table_filter_buttons'):
            for tree, button in self.table_filter_buttons.items(): button.configure(text=self.t('filter'))
        self.log_titles['events'].configure(text=self.t('consoleEvents'))
        # The main menu is rebuilt from the same display catalog as the controls.
        self.log_titles['progress'].configure(text=self.t(progress_title((self.last_view or {}).get('progress_source'))))
        if self.classic_pane:
            self.classic_pane.lang='zh' if locale=='zh-CN' else 'en';self.classic_pane._apply_language();self.classic_pane._refresh_tables_from_cache()
        try:self.preferences.save(language=locale)
        except (OSError,ValueError):self.status.set(self.t('saveFailed'))
        try:
            from .gui_settings import save_settings
            current = dict(self.app.desktop_shell_settings)
            current['language'] = locale
            self.app.desktop_shell_settings = save_settings(current)
        except (OSError,ValueError):self.status.set(self.t('saveFailed'))
        if self.last_view:
            self._render(self.last_view,language_only=True)
        else:
            # No Project/Owner snapshot exists in this state. Refresh only UI
            # empty-state text; preserve any selected Project and observations.
            for name,key in (("progress","noProgress"),("events","noEvents")):
                set_text(self.log_widgets[name],self.t(key))
            for box in (*self.detail_boxes.values(),self.result_box):
                set_text(box,self.t("chooseRun"))
            self._display_context()
        self.fit_toolbar_labels()

    def install_skin(self):
        from tkinter import filedialog, messagebox
        from .gui_settings import user_settings_path
        from .skin_system import install_skin
        source = filedialog.askdirectory(parent=self.app, title='Select declarative Skin folder')
        if not source:return
        try:
            skin_id = install_skin(source, user_settings_path().parent / 'skins')
            messagebox.showinfo('Skin installed', f"'{skin_id}' is installed. Select it in the Skin list.", parent=self.app)
            if self.skin_loader:
                self.skin_box.configure(values=(self.t('defaultLayout'),))
        except (OSError,ValueError) as exc:
            messagebox.showerror('Skin installation failed',str(exc),parent=self.app)

    def change_skin(self,skin_id):
        from tkinter import messagebox
        from .gui_settings import save_settings, user_settings_path
        from .skin_system import SkinLoader, apply_skin
        loader=SkinLoader(self.skin_loader.skins_root,extra_roots=self.skin_loader.extra_roots)
        try:skin=loader.load(skin_id)
        except ValueError as exc:
            messagebox.showerror('Skin',str(exc),parent=self.app);return
        try:
            current=dict(self.app.desktop_shell_settings);current['setGUIskin']=skin_id
            self.app.desktop_shell_settings=save_settings(current)
            self.app.desktop_skin=skin;self.app.skin_loader=loader;self.skin_loader=loader
            apply_skin(self.app,skin,appearance=self.app.desktop_shell_settings['appearance'])
            self.apply_typography()
            self.skin_var.set(self.t('defaultLayout'))
        except (OSError,ValueError) as exc:
            messagebox.showerror('Skin',str(exc),parent=self.app)

    def change_appearance(self,appearance):
        from .gui_settings import save_settings
        from .skin_system import apply_skin
        try:
            current=dict(self.app.desktop_shell_settings);current['appearance']=appearance
            self.app.desktop_shell_settings=save_settings(current)
            apply_skin(self.app,self.app.desktop_skin,appearance=appearance)
            self.apply_typography()
            self.appearance_var.set(appearance.title())
        except (OSError,ValueError) as exc:
            from tkinter import messagebox
            messagebox.showerror('Appearance',str(exc),parent=self.app)
        else:
            self.overview_message.set(self.t('welcomeText'))
            self.current_summary.set(self.t('chooseRun'))
            set_text(self.log_widgets['progress'],self.t('noProgress'))
            set_text(self.log_widgets['events'],self.t('noEvents'))
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
                if operation=='stop':
                    state=result.get('state','BLOCKED')
                    self.disconnect()
                    self.service_state=state
                    self.service_status.set(state+' · '+result.get('reason',''))
                    self.connection_code=state
                    self.status.set('Owner · '+state+' · IPC disconnected')
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
                self.run_items.update({r['run_id']:r for r in page['runs']})
                rows=[(r['run_id'],(r['run_id'],r.get('job_name') or r['job_id'],r['execution']+' / '+str(r.get('execution_phase') or ''))) for r in page['runs']]
                self.refresh_tables()
                self.page_counts.set(self.t('pageCounts',count=len(page['runs']),slot=page['slot_run_id'] or '—')+' · '+self.t('activeCount',count=sum(r['execution'] in {'START_INTENT','RUNNING','VALIDATING'} for r in page['runs'])))
                self.next_page=page['next_before_row'];self.older_button.configure(state='normal' if self.next_page is not None else 'disabled')
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
                self.render_rows=[(self.t('owner'),ep['owner_id']),('Job ID',run['job_id']),('Run ID',run['run_id']),
                    ('Plan ID',run.get('plan_id') or self.t('unavailable')),
                    ('Attempt',str(run.get('attempt_no')) if type(run.get('attempt_no')) is int else self.t('unavailable')),
                    ('Task Status',run.get('execution') or 'UNKNOWN'),('Phase',run.get('execution_phase') or self.t('unavailable')),
                    ('Backend',run.get('backend_id') or self.t('unavailable')),
                    (self.t('receipt'),value['receipt']['request_id'] if value['receipt'] else self.t('unavailable')),
                    ('Solver Conclusion',run.get('solver_conclusion') or 'NOT_RUN'),
                    ('Validation',run.get('artifact_validation') or 'NOT_RUN'),
                    ('Reconciliation',run.get('reconciliation') or 'UNKNOWN'),
                    ('ManagedScope', 'See Evidence' if run.get('managed_scope') else self.t('unavailable')),
                    (self.t('exitVerification'),run.get('exit_verification','UNKNOWN')),
                    (self.t('process'),run.get('managed_completion','NOT_CONFIRMED'))]
                attempts=[{'run_id':r.get('run_id'),'attempt_no':r.get('attempt_no'),
                           'execution':r.get('execution'),'plan_id':r.get('plan_id'),
                           'receipt_request_id':(r.get('receipt') or {}).get('request_id')}
                          for r in self.run_items.values() if r.get('job_id')==run.get('job_id')]
                attempts.sort(key=lambda item:(item.get('attempt_no') if type(item.get('attempt_no')) is int else -1,
                                               str(item.get('run_id') or '')))
                set_text(self.overview_cards['results'],summary+'\n\n'+self.t('scopeNote'))
                set_text(self.detail_boxes['identity'],summary+'\n\n'+self.t('identity')+'\n'+'\n'.join(k+': '+str(v) for k,v in self.render_rows)+'\n'+json_text({'run_id':run['run_id'],'plan_id':run['plan_id'],'backend_id':run['backend_id'],'receipt':value['receipt'],'gui_observed_at':self.last_update,'run_revision':run.get('revision'),'loaded_job_attempts':attempts,'attempt_history_scope':'loaded bounded ProjectView pages only; older attempts may not be loaded','read_consistency':'successive bounded API reads; not an atomic Run/events snapshot'}))
                set_text(self.detail_boxes['evidence'],self.t('diagnosis')+': '+name+'\n'+self.t('notAtomic')+'\n\n'+self.t('reason')+'\n'+json_text(diagnosis if diagnosis else {'unavailable':'CAPABILITY_UNAVAILABLE'})+'\n\n'+self.t('rawEvidence')+'\n'+json_text({k:run.get(k) for k in ('managed_scope','process_exits','overall_exit','reconciliation','administrative_closeout','recovery_scope_completion')}))
                set_text(self.detail_boxes['recovery'],self.t('approvalNote')+'\n\n'+(self.t('unavailableCapability')+'\n' if recovery.get('unavailable') else '')+json_text(recovery))
                set_text(self.result_box,summary+'\n\n'+self.t('resultNote')+'\n'+json_text(value['validations']))
            else:
                self.render_rows=[(self.t('owner'),ep['owner_id']),('Run ID','—')]
                for box in (*self.detail_boxes.values(),self.result_box):set_text(box,self.t('chooseRun'))
            self.log_titles['progress'].configure(text=self.t(progress_title(value.get('progress_source'))))
            self.log_titles['events'].configure(text=self.t('consoleEvents'))
            selected_events=[event for event in value['events'] if not self.selected_run_id or event.get('run_id')==self.selected_run_id]
            for name in self.log_widgets:
                box=self.log_widgets[name]
                if name=='events':
                    text='\n'.join(json.dumps(r,ensure_ascii=False) for r in selected_events) if selected_events else self.t('noEvents')
                else:
                    records=value['progress']
                    text='\n'.join(json.dumps(r,ensure_ascii=False) for r in records) if records else self.t('noProgress')
                    if value.get('log_error'):text=self.t('unavailable')+' · '+value['log_error']+'\n'+text
                set_text(box,text)
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
        if self.environment_dialog and self.environment_dialog.winfo_exists():
            self.environment_dialog.close()
        if self.environment_thread and self.environment_thread.is_alive():
            self.environment_thread.join(5)
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
