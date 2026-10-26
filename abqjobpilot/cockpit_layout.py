"""Compact native presentation only. Actions stay in DesktopWorkspace/public clients."""
import re
import tkinter as tk
from tkinter import ttk, scrolledtext
from .ui_resources import LANGUAGES


def build_cockpit(w):
    app=w.app
    app.title('AbqJobPilot · Execution Workspace');app._apply_icon();app._set_initial_geometry()
    app._configure_styles();app.minsize(1024,700)
    geometry=w.preferences.data.get('geometry','')
    if isinstance(geometry,str) and re.fullmatch(r'\d{3,4}x\d{3,4}[+-]\d+[+-]\d+',geometry):app.geometry(geometry)
    style=ttk.Style(app)
    style.configure('Cockpit.Treeview',font=('Segoe UI',10),rowheight=27)
    style.configure('Cockpit.Treeview.Heading',font=('Segoe UI',10,'bold'),padding=(5,5))
    style.map('Cockpit.Treeview',background=[('selected','#d9e9f6')],foreground=[('selected','#122c43')])
    style.configure('Cockpit.TButton',font=('Segoe UI',10),padding=(10,5))
    app.columnconfigure(0,weight=1);app.rowconfigure(1,weight=1)
    top=ttk.Frame(app,padding=(10,6));top.grid(row=0,column=0,sticky='ew');top.columnconfigure(1,weight=1)
    ttk.Label(top,text='AbqJobPilot',font=('Segoe UI',13,'bold')).grid(row=0,column=0,padx=(0,16))
    w.project_menu=tk.Menu(top,tearoff=False)
    w.project_selector=ttk.Menubutton(top,textvariable=w.project_label,menu=w.project_menu,width=25)
    w.project_selector.grid(row=0,column=1,sticky='w')
    w.command_button=w.button(top,'agentCommand',w.show_command);w.command_button.grid(row=0,column=2,padx=5)
    w.classic_button=w.button(top,'classic',lambda:w.navigate('classic'));w.classic_button.grid(row=0,column=3,padx=5)
    w.language_var=tk.StringVar(value=LANGUAGES[w.locale])
    w.language_box=ttk.Combobox(top,values=list(LANGUAGES.values()),textvariable=w.language_var,state='readonly',width=20)
    w.language_box.grid(row=0,column=4,padx=(10,0))
    w.language_box.bind('<<ComboboxSelected>>',lambda _:w.change_language(next(k for k,v in LANGUAGES.items() if v==w.language_var.get())))
    w.content=ttk.Frame(app,padding=(8,0));w.content.grid(row=1,column=0,sticky='nsew');w.content.columnconfigure(0,weight=1);w.content.rowconfigure(2,weight=1)
    w.content.bind('<Configure>',w._resize_text,add='+')
    bar=ttk.Frame(w.content,padding=(4,4));bar.grid(row=0,column=0,sticky='ew');bar.columnconfigure(0,weight=1)
    ttk.Label(bar,textvariable=w.status,font=('Segoe UI',10)).grid(row=0,column=0,sticky='w')
    ttk.Label(bar,textvariable=w.resource,font=('Segoe UI',10)).grid(row=0,column=1,sticky='e')
    w.page_counts=tk.StringVar(value='—')
    ttk.Label(bar,textvariable=w.page_counts,foreground='#536778').grid(row=1,column=0,sticky='w')
    ttk.Label(bar,textvariable=w.freshness,foreground='#536778').grid(row=1,column=1,sticky='e')
    summary=ttk.Frame(w.content,padding=(6,7));summary.grid(row=1,column=0,sticky='ew');summary.columnconfigure(0,weight=1)
    w.current_panel=summary
    w.current_summary=tk.StringVar(value=w.t('chooseRun'));w.current_dimensions=tk.StringVar(value='—')
    ttk.Label(summary,textvariable=w.current_summary,font=('Segoe UI',10,'bold'),wraplength=1100).grid(row=0,column=0,sticky='w')
    ttk.Label(summary,textvariable=w.current_dimensions,font=('Segoe UI',10),wraplength=1100).grid(row=1,column=0,sticky='w',pady=(4,0))
    w.button(summary,'evidence',lambda:w.show_command('runs')).grid(row=0,column=1,rowspan=2,padx=6)
    host=ttk.Frame(w.content);host.grid(row=2,column=0,sticky='nsew');host.columnconfigure(0,weight=1);host.rowconfigure(0,weight=1)
    w.pane=ttk.PanedWindow(host,orient='vertical');w.pane.grid(row=0,column=0,sticky='nsew')
    w.pages_host=ttk.Frame(w.pane);w.pages_host.columnconfigure(0,weight=1);w.pages_host.rowconfigure(0,weight=1);w.pane.add(w.pages_host,weight=3)
    workspace=ttk.Frame(w.pages_host);workspace.grid(row=0,column=0,sticky='nsew');workspace.columnconfigure(0,weight=1);workspace.rowconfigure(1,weight=1)
    w.pages={'overview':workspace,'queue':workspace}
    welcome=ttk.Frame(workspace,padding=(4,5));welcome.grid(row=0,column=0,sticky='ew');welcome.columnconfigure(0,weight=1)
    w.overview_message=tk.StringVar(value=w.t('welcomeText'))
    ttk.Label(welcome,textvariable=w.overview_message,wraplength=680).grid(row=0,column=0,sticky='w')
    w.new_button=w.button(welcome,'new',w.new_project);w.new_button.grid(row=0,column=1,padx=4)
    w.choose_button=w.button(welcome,'open',w.choose_project);w.choose_button.grid(row=0,column=2,padx=4)
    w.overview_split=ttk.PanedWindow(workspace,orient='horizontal');w.overview_split.grid(row=1,column=0,sticky='nsew');w.run_split=w.overview_split
    w.filters={};w.sorting={}
    for name,columns,keys in [('queue',('job','state','run'),('job','stage','runs')),('results',('job','state','solver','validation','run'),('job','stage','solver','validation','runs'))]:
        panel=ttk.Frame(w.overview_split,padding=4);panel.columnconfigure(0,weight=1);panel.rowconfigure(1,weight=1);w.overview_split.add(panel,weight=1)
        header=ttk.Frame(panel);header.grid(row=0,column=0,sticky='ew');header.columnconfigure(1,weight=1)
        w.label(header,name,font=('Segoe UI',11,'bold')).grid(row=0,column=0,sticky='w',padx=(0,10))
        search=tk.StringVar();entry=ttk.Entry(header,textvariable=search,width=18);entry.grid(row=0,column=1,sticky='ew')
        w.label(header,'filter').grid(row=0,column=2,padx=5)
        holder,tree=w.tree(panel,columns,keys);holder.grid(row=1,column=0,sticky='nsew',pady=(6,0));tree.configure(style='Cockpit.Treeview')
        for i,col in enumerate(columns):
            tree.column(col,width=180 if col=='job' else 170 if col=='run' else 160,minwidth=170 if col=='run' else 85)
            tree.heading(col,command=lambda t=tree,n=i:w.sort_table(t,n))
        tree.tag_configure('failed',foreground='#a33232');tree.tag_configure('unknown',foreground='#976000');tree.tag_configure('running',foreground='#17618d')
        tree.bind('<<TreeviewSelect>>',lambda _,t=tree:w.select_from(t))
        w.filters[tree]=search;w.sorting[tree]=(0,False);search.trace_add('write',lambda *_:w.refresh_tables())
        setattr(w,name+'_tree',tree)
    w.run_tree=w.queue_tree
    pagination=ttk.Frame(workspace);pagination.grid(row=2,column=0,sticky='e')
    w.button(pagination,'firstPage',lambda:w.page(0)).pack(side='left')
    w.older_button=w.button(pagination,'older',lambda:w.page(w.next_page));w.older_button.pack(side='left');w.older_button.configure(state='disabled')
    w.overview_split.grid_remove()
    classic=ttk.Frame(w.pages_host,padding=4);classic.grid(row=0,column=0,sticky='nsew');classic.rowconfigure(2,weight=1);classic.columnconfigure(0,weight=1);w.pages['classic']=classic
    bar=ttk.Frame(classic);bar.grid(row=0,column=0,sticky='ew')
    w.back_button=w.button(bar,'executionWorkspace',lambda:w.navigate('runs'));w.back_button.pack(side='left')
    w.button(bar,'classicOpen',w.choose_classic).pack(side='left',padx=6)
    w.classic_note=w.label(classic,'classicSelect',wraplength=950);w.classic_note.grid(row=1,column=0,sticky='w')
    w.classic_host=ttk.Frame(classic);w.classic_host.grid(row=2,column=0,sticky='nsew');w.classic_host.rowconfigure(0,weight=1);w.classic_host.columnconfigure(0,weight=1)
    w.logs=ttk.PanedWindow(w.pane,orient='horizontal');w.pane.add(w.logs,weight=2)
    w.log_widgets={};w.follow={};w.log_titles={}
    for name,key in [('progress','progressUnavailable'),('events','serviceEvents')]:
        panel=ttk.Frame(w.logs,padding=4);panel.rowconfigure(1,weight=1);panel.columnconfigure(0,weight=1);w.logs.add(panel,weight=1)
        bar=ttk.Frame(panel);bar.grid(row=0,column=0,sticky='ew');title=ttk.Label(bar,text=w.t(key),font=('Segoe UI',10,'bold'));title.pack(side='left');w.log_titles[name]=title
        w.follow[name]=tk.BooleanVar(value=True)
        check=ttk.Checkbutton(bar,variable=w.follow[name],command=lambda n=name:w.log_widgets[n].see('end') if w.follow[n].get() else None);w.bind_text(check,'follow');check.pack(side='right')
        box=scrolledtext.ScrolledText(panel,height=9,state='disabled',wrap='none',font=('Consolas',10),background='#fafbfc',foreground='#213244',relief='flat',borderwidth=1)
        box.grid(row=1,column=0,sticky='nsew');w.log_widgets[name]=box
        horizontal=ttk.Scrollbar(panel,orient='horizontal',command=box.xview);horizontal.grid(row=2,column=0,sticky='ew');box.configure(xscrollcommand=horizontal.set)
        box.bind('<MouseWheel>',lambda _,n=name:w.follow[n].set(False),add='+');box.vbar.bind('<ButtonPress-1>',lambda _,n=name:w.follow[n].set(False),add='+')
    # Advanced commands share the same Reader and selected Run; no separate execution adapter.
    w.drawer=ttk.Frame(host,padding=8,width=440);w.drawer.grid(row=0,column=1,sticky='ns');w.drawer.grid_propagate(False);w.drawer.rowconfigure(1,weight=1);w.drawer.columnconfigure(0,weight=1)
    bar=ttk.Frame(w.drawer);bar.grid(row=0,column=0,sticky='ew');bar.columnconfigure(0,weight=1)
    w.command_var=tk.StringVar(value=w.t('command.service'));w.command_keys=('service','runs','recovery','agent','settings')
    selector=ttk.Combobox(bar,textvariable=w.command_var,state='readonly',values=[w.t('command.'+k) for k in w.command_keys]);selector.grid(row=0,column=0,sticky='ew')
    selector.bind('<<ComboboxSelected>>',lambda _:w.show_command(w.command_keys[selector.current()]));w.command_selector=selector
    w.button(bar,'close',lambda:w.drawer.grid_remove()).grid(row=0,column=1,padx=4)
    w.command_panels={};w.page_bodies={};w.scroll_pages=[];w.nav={}
    for key in w.command_keys:
        panel=ttk.Frame(w.drawer);panel.grid(row=1,column=0,sticky='nsew');panel.columnconfigure(0,weight=1);panel.rowconfigure(0,weight=1)
        canvas=tk.Canvas(panel,highlightthickness=0);canvas.grid(row=0,column=0,sticky='nsew')
        scroll=ttk.Scrollbar(panel,orient='vertical',command=canvas.yview);scroll.grid(row=0,column=1,sticky='ns');canvas.configure(yscrollcommand=scroll.set)
        inner=ttk.Frame(canvas,padding=(2,8));window=canvas.create_window(0,0,window=inner,anchor='nw')
        canvas.bind('<Configure>',lambda e,c=canvas,i=window:c.itemconfigure(i,width=e.width));inner.bind('<Configure>',lambda e,c=canvas:c.configure(scrollregion=c.bbox('all')))
        w.command_panels[key]=panel;w.page_bodies[key]=inner;w.pages[key]=workspace
    w.pages['projects']=workspace
    f=w.page_bodies['service']
    ttk.Label(f,textvariable=w.identity,wraplength=380).pack(anchor='w',pady=5)
    w.button(f,'projectSettings',w.project_settings).pack(anchor='w')
    ttk.Label(f,textvariable=w.service_status,wraplength=380).pack(anchor='w',pady=8)
    bar=ttk.Frame(f);bar.pack(fill='x')
    for n,(key,cmd) in enumerate([('start',lambda:w.lifecycle_action('start')),('reconnect',w.reconnect),('disconnect',w.disconnect),('stop',w.stop_service)]):
        button=w.button(bar,key,cmd);button.grid(row=n//2,column=n%2,sticky='ew',pady=3);setattr(w,key+'_button',button)
    w.label(f,'noAuto',wraplength=380).pack(anchor='w',pady=5);w.service_box=w.text(f)
    h,w.recent_tree=w.tree(f,('path',),('recent',));h.pack(fill='both',expand=True,pady=8);w.recent_tree.bind('<Double-1>',w.open_recent);w.recent_tree.bind('<Return>',w.open_recent)
    w.detail_boxes={};w.overview_cards={}
    f=w.page_bodies['runs']
    style.layout('Inspector.TNotebook.Tab',[])
    sections=('identity','evidence','recovery','queue','results')
    w.inspector_selector=ttk.Combobox(f,state='readonly',values=[w.t(k) for k in sections]);w.inspector_selector.pack(fill='x',pady=(0,6));w.inspector_selector.current(0)
    w.details=ttk.Notebook(f,style='Inspector.TNotebook');w.details.pack(fill='both',expand=True)
    w.inspector_selector.bind('<<ComboboxSelected>>',lambda _:w.details.select(w.inspector_selector.current()))
    for key in ('identity','evidence','recovery'):
        panel=ttk.Frame(w.details);w.details.add(panel,text=w.t(key));w.tab_labels.append((w.details,panel,key));w.detail_boxes[key]=w.text(panel)
    for key in ('queue','results'):
        panel=ttk.Frame(w.details);w.details.add(panel,text=w.t(key));w.tab_labels.append((w.details,panel,key));w.overview_cards[key]=w.text(panel)
    w.result_box=w.overview_cards['results']
    for box in (*w.detail_boxes.values(),*w.overview_cards.values()):box.configure(height=24)
    f=w.page_bodies['recovery'];w.label(f,'approvalNote',wraplength=380).pack(anchor='w',pady=8)
    w.button(f,'evidence',lambda:(w.show_command('runs'),w.details.select(2))).pack(anchor='w')
    w.label(f,'noAuto',wraplength=380).pack(anchor='w',pady=8)
    w.recovery_box=w.text(f);w.recovery_box.configure(height=24)
    f=w.page_bodies['agent']
    for key in ('permission','pythonText','cliText','mcpText','secretText'):w.label(f,key,wraplength=380).pack(anchor='w',pady=6)
    ttk.Label(f,text='MCP (read / preview)\nabq_preflight · abq_list_jobs\nabq_job_status · abq_locate_outputs\nabq_prepare_enqueue',font=('Consolas',10)).pack(anchor='w',pady=6)
    w.button(f,'documentation',w.show_api).pack(anchor='w')
    f=w.page_bodies['settings']
    for key in ('languageNote','coverage','reviewPending','classicFallback','layoutNote'):w.label(f,key,wraplength=380).pack(anchor='w',pady=6)
    w.button(f,'resetLayout',lambda:w.restore_layout(default=True)).pack(anchor='w')
    w.drawer.grid_remove()
    footer=ttk.Frame(app,padding=(10,3));footer.grid(row=2,column=0,sticky='ew')
    w.label(footer,'closeNote',wraplength=980).pack(side='left')
