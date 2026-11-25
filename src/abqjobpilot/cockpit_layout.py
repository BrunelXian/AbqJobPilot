"""Compact native presentation only. Actions stay in DesktopWorkspace/public clients."""
import re
import tkinter as tk
from tkinter import ttk, scrolledtext
from .ui_resources import LANGUAGES


def build_cockpit(w):
    app=w.app
    app.title('AbqJobPilot · Execution Workspace');app._apply_icon();app._set_initial_geometry()
    app._configure_styles();app.minsize(1024,700)
    geometry=w.preferences.data.get('geometry','') if app.desktop_shell_settings.get('restore_window',True) else ''
    if isinstance(geometry,str) and re.fullmatch(r'\d{3,4}x\d{3,4}[+-]\d+[+-]\d+',geometry):app.geometry(geometry)
    style=ttk.Style(app)
    style.configure('Cockpit.Treeview',font=('Segoe UI',10),rowheight=28)
    style.configure('Cockpit.Treeview.Heading',font=('Segoe UI Semibold',10),padding=(6,6))
    style.map('Cockpit.Treeview',background=[('selected','#d9e9f6')],foreground=[('selected','#122c43')])
    style.configure('TButton',font=('Segoe UI',10),padding=(12,6))
    app.columnconfigure(0,weight=1);app.rowconfigure(1,weight=1)
    top=ttk.Frame(app,padding=(10,5));top.grid(row=0,column=0,sticky='ew');top.columnconfigure(4,weight=1)
    w.project_menu=tk.Menu(top,tearoff=False)
    w.project_selector=ttk.Menubutton(top,textvariable=w.project_label,menu=w.project_menu,width=17)
    w.project_selector.grid(row=0,column=0,sticky='w',padx=(0,5))
    actions=ttk.Frame(top);actions.grid(row=0,column=1,sticky='w')
    toolbar_gap=2 if getattr(getattr(app,'desktop_skin',None),'layout',{}).get('compact_toolbar',True) else 5
    w.add_task_button=w.button(actions,'addTaskAction',lambda:None);w.add_task_button.grid(row=0,column=0,padx=(0,toolbar_gap))
    w.command_button=w.button(actions,'agentCommand',w.open_agent_command);w.command_button.grid(row=0,column=1,padx=toolbar_gap)
    w.start_queue_button=w.button(actions,'startQueueAction',lambda:None);w.start_queue_button.grid(row=0,column=2,padx=toolbar_gap)
    w.service_toolbar_button=w.button(actions,'service',lambda:w.show_command('service'));w.service_toolbar_button.grid(row=0,column=3,padx=(toolbar_gap,0))
    w.add_task_button.configure(command=w.add_test_task);w.start_queue_button.configure(command=w.submit_test_task)
    button_width=getattr(getattr(app,'desktop_skin',None),'layout',{}).get('toolbar_button_width',12)
    w.command_button.configure(width=max(13,button_width));w.add_task_button.configure(width=-1)
    w.start_queue_button.configure(width=-1);w.service_toolbar_button.configure(width=10)
    w.skin_var=tk.StringVar(value=w.t('defaultLayout'))
    prefs=ttk.Frame(top);prefs.grid(row=0,column=4,sticky='e')
    w.skin_box=ttk.Combobox(prefs,values=(w.t('defaultLayout'),),textvariable=w.skin_var,state='readonly',width=max(10,len(w.t('defaultLayout'))))
    w.skin_box.grid(row=0,column=0,padx=(4,0));w.skin_box.bind('<<ComboboxSelected>>',lambda _:w.change_skin('default'))
    w.language_var=tk.StringVar(value=LANGUAGES[w.locale])
    w.language_box=ttk.Combobox(prefs,values=list(LANGUAGES.values()),textvariable=w.language_var,state='readonly',width=10)
    w.language_box.grid(row=0,column=1,padx=(4,0))
    w.language_box.bind('<<ComboboxSelected>>',lambda _:w.change_language(next(k for k,v in LANGUAGES.items() if v==w.language_var.get())))
    w.appearance_var=tk.StringVar(value=app.desktop_shell_settings['appearance'].title())
    w.appearance_box=ttk.Combobox(prefs,values=('Light','Dark'),textvariable=w.appearance_var,state='readonly',width=6)
    w.appearance_box.grid(row=0,column=2,padx=(4,0));w.appearance_box.bind('<<ComboboxSelected>>',lambda _:w.change_appearance(w.appearance_var.get().lower()))
    menubar=tk.Menu(app,tearoff=False)
    w.project_bar_menu=tk.Menu(menubar,tearoff=False)
    menubar.add_cascade(label=w.t('menu.project'),menu=w.project_bar_menu)
    task_menu=tk.Menu(menubar,tearoff=False);task_menu.add_command(label=w.t('addTaskDisabled'),state='disabled');task_menu.add_command(label=w.t('startQueueDisabled'),state='disabled');menubar.add_cascade(label=w.t('menu.task'),menu=task_menu);w.task_menu=task_menu
    view_menu=tk.Menu(menubar,tearoff=False)
    for label,key in (('overview','overview'),('projects','projects'),('queue','queue'),('runs','runs'),('results','results')):view_menu.add_command(label=w.t(label),command=lambda page=key:w.navigate(page))
    menubar.add_cascade(label=w.t('menu.view'),menu=view_menu);w.view_menu=view_menu
    tools_menu=tk.Menu(menubar,tearoff=False);tools_menu.add_command(label=w.t('reconnect')+' Owner',command=w.reconnect);tools_menu.add_command(label=w.t('refresh'),command=w.reconnect);menubar.add_cascade(label=w.t('menu.tools'),menu=tools_menu);w.tools_menu=tools_menu
    agent_menu=tk.Menu(menubar,tearoff=False);agent_menu.add_command(label=w.t('agentCommand'),command=w.open_agent_command);agent_menu.add_command(label=w.t('agent'),command=lambda:w.navigate('agent'));menubar.add_cascade(label=w.t('menu.agent'),menu=agent_menu);w.agent_menu=agent_menu
    help_menu=tk.Menu(menubar,tearoff=False);help_menu.add_command(label=w.t('menu.about'),command=lambda:w.show_command('settings'));menubar.add_cascade(label=w.t('menu.help'),menu=help_menu);w.help_menu=help_menu
    app.configure(menu=menubar);w.menu_bar=menubar
    w.content=ttk.Frame(app,padding=(8,0));w.content.grid(row=1,column=0,sticky='nsew');w.content.columnconfigure(0,weight=1);w.content.rowconfigure(1,weight=1)
    w.content.bind('<Configure>',w._resize_text,add='+')
    bar=ttk.Frame(w.content,padding=(4,2));bar.grid(row=0,column=0,sticky='ew');bar.columnconfigure(0,weight=1)
    ttk.Label(bar,textvariable=w.status).grid(row=0,column=0,sticky='w')
    ttk.Label(bar,textvariable=w.resource).grid(row=0,column=1,sticky='e')
    w.page_counts=tk.StringVar(value='')
    summary=ttk.Frame(w.content,padding=(0,0));w.current_panel=None
    w.current_summary=tk.StringVar(value=w.t('chooseRun'));w.current_dimensions=tk.StringVar(value='—')
    ttk.Label(summary,textvariable=w.current_summary,font=('Segoe UI',10,'bold'),wraplength=1100).grid(row=0,column=0,sticky='w')
    ttk.Label(summary,textvariable=w.current_dimensions,font=('Segoe UI',10),wraplength=1100).grid(row=1,column=0,sticky='w',pady=(4,0))
    w.button(summary,'evidence',lambda:w.show_command('runs')).grid(row=0,column=1,rowspan=2,padx=6)
    host=ttk.Frame(w.content);host.grid(row=1,column=0,sticky='nsew');host.columnconfigure(0,weight=1);host.rowconfigure(0,weight=1)
    w.pane=ttk.PanedWindow(host,orient='vertical');w.pane.grid(row=0,column=0,sticky='nsew')
    w.pages_host=ttk.Frame(w.pane);w.pages_host.columnconfigure(0,weight=1);w.pages_host.rowconfigure(0,weight=1);w.pane.add(w.pages_host,weight=3)
    workspace=ttk.Frame(w.pages_host);workspace.grid(row=0,column=0,sticky='nsew');workspace.columnconfigure(0,weight=1);workspace.rowconfigure(0,weight=1)
    w.current_panel=workspace
    w.pages={'overview':workspace,'queue':workspace}
    welcome=ttk.Frame(workspace,padding=(0,0));welcome.grid_remove();welcome.columnconfigure(0,weight=1)
    w.overview_message=tk.StringVar(value=w.t('welcomeText'))
    ttk.Label(welcome,textvariable=w.overview_message,wraplength=680).grid(row=0,column=0,sticky='w')
    w.new_button=w.button(welcome,'new',w.new_project);w.choose_button=w.button(welcome,'open',w.choose_project)
    w.overview_split=ttk.PanedWindow(workspace,orient='horizontal');w.overview_split.grid(row=0,column=0,sticky='nsew');w.run_split=w.overview_split
    w.filters={};w.sorting={};w.table_filter_buttons={};w.table_counts={};w.filter_windows={}
    for name,columns,keys in [
        ('queue',('index','status','job','batch','strategy','cpus','gpus'),('index','status','jobName','batch','strategy','cpus','gpus')),
        ('results',('status','job','batch','strategy','ended','duration','warnings'),('status','jobName','batch','strategy','ended','duration','warnings'))]:
        panel=ttk.Frame(w.overview_split,padding=4);panel.columnconfigure(0,weight=1);panel.rowconfigure(1,weight=1);w.overview_split.add(panel,weight=1)
        header=ttk.Frame(panel);header.grid(row=0,column=0,sticky='ew');header.columnconfigure(1,weight=1)
        w.label(header,name,style='Cockpit.Header.TLabel').grid(row=0,column=0,sticky='w',padx=(0,6))
        count=tk.StringVar(value='0');ttk.Label(header,textvariable=count).grid(row=0,column=2,sticky='e',padx=(0,5));w.table_counts[name]=count
        search=tk.StringVar();button=ttk.Button(header,text=w.t('filter'),command=lambda n=name:w.open_table_filter(n));button.grid(row=0,column=3,sticky='e')
        if name=='queue':
            w.older_button=w.button(header,'older',lambda:w.page(w.next_page));w.older_button.grid(row=0,column=4,sticky='e',padx=(4,0));w.older_button.configure(state='disabled')
        holder,tree=w.tree(panel,columns,keys);holder.grid(row=1,column=0,sticky='nsew',pady=(6,0));tree.configure(style='Cockpit.Treeview')
        for i,col in enumerate(columns):
            tree.column(col,width=170 if col=='job' else 115,minwidth=95 if col!='job' else 140,stretch=col=='job')
            tree.heading(col,command=lambda t=tree,n=i:w.sort_table(t,n))
        tree.tag_configure('failed',foreground='#a33232');tree.tag_configure('unknown',foreground='#976000');tree.tag_configure('running',foreground='#17618d')
        tree.bind('<<TreeviewSelect>>',lambda _,t=tree:w.select_from(t))
        w.filters[tree]=search;w.sorting[tree]=(0,False);search.trace_add('write',lambda *_:w.refresh_tables())
        w.table_filter_buttons[tree]=button
        setattr(w,name+'_tree',tree)
    w.run_tree=w.queue_tree
    classic=ttk.Frame(w.pages_host,padding=4);classic.grid(row=0,column=0,sticky='nsew');classic.rowconfigure(2,weight=1);classic.columnconfigure(0,weight=1);w.pages['classic']=classic
    bar=ttk.Frame(classic);bar.grid(row=0,column=0,sticky='ew')
    w.back_button=w.button(bar,'executionWorkspace',lambda:w.navigate('runs'));w.back_button.pack(side='left')
    w.button(bar,'classicOpen',w.choose_classic).pack(side='left',padx=6)
    w.classic_note=w.label(classic,'classicSelect',wraplength=950);w.classic_note.grid(row=1,column=0,sticky='w')
    w.classic_host=ttk.Frame(classic);w.classic_host.grid(row=2,column=0,sticky='nsew');w.classic_host.rowconfigure(0,weight=1);w.classic_host.columnconfigure(0,weight=1)
    w.logs=ttk.PanedWindow(w.pane,orient='horizontal');w.pane.add(w.logs,weight=2)
    w.log_widgets={};w.follow={};w.log_titles={}
    for name,key in [('progress','progressUnavailable'),('events','consoleEvents')]:
        panel=ttk.Frame(w.logs,padding=4);panel.rowconfigure(1,weight=1);panel.columnconfigure(0,weight=1);w.logs.add(panel,weight=1)
        bar=ttk.Frame(panel);bar.grid(row=0,column=0,sticky='ew');title=ttk.Label(bar,text=w.t(key),style='Cockpit.Header.TLabel');title.pack(side='left');w.log_titles[name]=title
        w.follow[name]=tk.BooleanVar(value=True)
        check=ttk.Checkbutton(bar,variable=w.follow[name],command=lambda n=name:w.log_widgets[n].see('end') if w.follow[n].get() else None);w.bind_text(check,'follow');check.pack(side='right')
        box=scrolledtext.ScrolledText(panel,height=9,state='disabled',wrap='none',font=('Consolas',10),background='#fafbfc',foreground='#213244',relief='flat',borderwidth=1)
        box.grid(row=1,column=0,sticky='nsew');w.log_widgets[name]=box
        box.bind('<Control-c>',lambda event,b=box:w.copy_text(b),add='+')
        box.bind('<Control-C>',lambda event,b=box:w.copy_text(b),add='+')
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
    for n,(key,cmd) in enumerate([('start',w.start_service),('reconnect',w.reconnect),('disconnect',w.disconnect),('stop',w.stop_service)]):
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
    w.button(f,'abaqusEnvironments',w.show_environments).pack(anchor='w',pady=8)
    build=app.build_metadata
    ttk.Label(f,text=f"{build['product']} {build['version']} · {build['runtime_mode']} · Build {build['build_id']} · Python {build['python']} · Skin API {build['skin_api_version']}",wraplength=380).pack(anchor='w',pady=6)
    for key in ('languageNote','coverage','reviewPending','classicFallback','layoutNote'):w.label(f,key,wraplength=380).pack(anchor='w',pady=6)
    ttk.Label(f,text='Install declaration-only Skins under the per-user AbqJobPilot/skins folder, then select one above.',wraplength=380).pack(anchor='w',pady=6)
    ttk.Button(f,text='Install Skin',command=w.install_skin).pack(anchor='w')
    w.button(f,'resetLayout',lambda:w.restore_layout(default=True)).pack(anchor='w')
    w.drawer.grid_remove()
    footer=ttk.Frame(app,padding=(0,0));footer.grid_remove()
    w.label(footer,'closeNote',wraplength=980).pack(side='left')
