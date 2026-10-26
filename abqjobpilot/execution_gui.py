"""Public monitoring and explicit product/lifecycle actions in the existing GUI.

Monitoring uses bounded public reads. New invokes the shared project core;
Start/Stop use the shared lifecycle manager. No direct SQL, Backend, approval or
legacy Runtime access. Views are successive observations, not an atomic snapshot.
"""
from collections import deque
from datetime import datetime
import json
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

from . import __version__
from .execution.client import FakeClient
from .execution.models import ExecutionError, fields, require, text
from .execution.paths import local_path, no_reparse

CONNECTION_REASONS = {
    'RECONNECTING':'正在重新核对 Project 与 owner',
    'NOT_FOUND':'未找到所选 Project 的必要文件或连接材料',
    'DISCOVERY_UNAVAILABLE':'未取得该实例的有效连接材料；请检查服务和私有连接文件',
    'DISCOVERY_LAYOUT_UNSUPPORTED':'不支持此实例目录布局，请检查显式实例根',
    'UNSUPPORTED_FORMAT':'Project／存储格式不兼容；不会迁移或初始化',
    'PROJECT_IDENTITY_MISMATCH':'Project 身份不匹配，拒绝连接',
    'ENDPOINT_IDENTITY_MISMATCH':'连接信息与目标 owner 不一致或已过期',
    'PROCESS_IDENTITY_MISMATCH':'PID 对应的创建身份不匹配，拒绝连接',
    'PROCESS_IDENTITY_UNKNOWN':'无法核实记录的 owner 进程身份',
    'OWNER_NOT_RUNNING':'记录的 owner 已退出；不会启动替代服务',
    'PROTOCOL_MISMATCH':'服务协议不兼容',
    'CAPABILITY_UNAVAILABLE':'现有服务缺少 Run 列表能力；不会自动重启',
    'AUTHENTICATION_FAILED':'连接认证失败，请核对该实例的私有连接材料',
    'COMMUNICATION_UNKNOWN':'服务不可达或请求超时；任务状态保持未知',
    'STORE_REQUIRES_MAINTENANCE':'存储要求显式维护；只读连接不修复',
    'LIMIT_EXCEEDED':'查询超过安全限额；没有静默截断',
    'LOCAL_CREDENTIAL_UNAVAILABLE':'本机用户凭据不可用；副本、移动或更换用户需显式重新配置，不自动连接原实例',
    'PROJECT_INCOMPLETE':'Project 创建未完成；不会自动修复或启动',
    'LEGACY_PROJECT':'这是 Legacy Project，请使用独立的 Legacy 入口',
    'NOT_AN_AGENT_FIRST_PROJECT':'普通文件夹尚未初始化；打开操作不会创建 Project',
}


def read_connection(path):
    path = local_path(path)
    no_reparse(path)
    with path.open('rb') as stream:
        raw = stream.read(65537)
    require(len(raw) <= 65536, 'LIMIT_EXCEEDED', 'Connection material exceeds bound')
    value = json.loads(raw)
    fields(value, ('endpoint', 'credential'))
    return FakeClient(value['endpoint'], value['credential'])


class Reader:
    def __init__(self, connection, request_key, *, project=None, diagnostics=False):
        if project is None: text(request_key)
        self.connection, self.key = connection, request_key
        self.project = project
        self.diagnostics = diagnostics
        self.selection_lock = threading.Lock()
        self.selection = None
        self.before_row = 0
        self.selection_version = 0
        self.stop = threading.Event()
        self.views = queue.Queue(maxsize=1)
        self.thread = threading.Thread(target=self._loop, name='execution-public-reader')
        self.thread.start()

    def select(self, item):
        with self.selection_lock:
            self.selection = item
            self.selection_version += 1

    def page(self, before_row):
        with self.selection_lock:
            self.before_row = before_row
            self.selection_version += 1

    def _publish(self, value):
        try: self.views.get_nowait()
        except queue.Empty: pass
        self.views.put_nowait(value)

    def _loop(self):
        progress, events = deque(maxlen=128), deque(maxlen=64)
        pcursor = ecursor = 0
        owner = None
        project_binding = None
        selected_run = None
        while not self.stop.is_set():
            try:
                with self.selection_lock:
                    selection, before_row, version = self.selection, self.before_row, self.selection_version
                health = None
                if self.project:
                    from .service_discovery import discover
                    client, context, health = discover(self.project, self.connection)
                else: client = read_connection(self.connection)
                binding = tuple(client.endpoint[k] for k in ('project_id','project_instance_id','context_digest'))
                if project_binding is None: project_binding = binding
                require(binding == project_binding, 'PROJECT_IDENTITY_MISMATCH', 'Connection file changed Project')
                # Explicitly supplied connection material is the only discovery source.
                if owner != client.endpoint['owner_id']:
                    progress.clear(); events.clear(); pcursor = ecursor = 0
                    owner = client.endpoint['owner_id']
                def call(fn, *args):
                    if self.stop.is_set(): raise InterruptedError()
                    return fn(*args)
                health = health or call(client.health)
                project_page = call(client.project_view, before_row, 32) if self.project else None
                if self.project:
                    receipt = selection['receipt'] if selection else None
                else:
                    try: receipt = call(client.receipt, self.key)
                    except ExecutionError as exc:
                        if exc.code != 'NOT_FOUND': raise
                        receipt = None
                gate = project_page['gate'] if project_page else call(client.dispatch_gate)
                run = call(client.run, receipt['run_id']) if receipt else None
                if selected_run != (run['run_id'] if run else None):
                    progress.clear(); events.clear(); pcursor = ecursor = 0
                    selected_run = run['run_id'] if run else None
                validations = call(client.validations, run['run_id']) if run else []
                recovery = interruption = None
                if run and self.diagnostics:
                    for operation in ('inspect_interrupted_execution', 'preview_interrupted_recovery'):
                        result = {'unavailable': 'CAPABILITY_UNAVAILABLE'}
                        if operation in health.get('operations', []):
                            try: result = call(getattr(client, operation), run['run_id'])
                            except ExecutionError as exc: result = {'unavailable': exc.code}
                        if operation == 'inspect_interrupted_execution': interruption = result
                        else: recovery = result
                closeout = None
                if run and run.get('backend_id') == 'abaqus-standard-axial-2024-v1' and 'preview_closeout' in health.get('operations',[]):
                    try: closeout = call(client.preview_closeout, run['run_id'])
                    except ExecutionError as exc:
                        if exc.code in {'COMMUNICATION_UNKNOWN','ENDPOINT_IDENTITY_MISMATCH','AUTHENTICATION_FAILED'}: raise
                        closeout = {'unavailable':exc.code}
                log_error = None
                progress_source = None
                if run:
                    try:
                        page = call(client.progress, run['run_id'], pcursor, 64)
                        progress_source = page.get('source')
                        if page.get('source') == 'bounded_standard_text_latest': progress.clear()
                        progress.extend(page['records']); pcursor = page['next_sequence']
                    except ExecutionError as exc:
                        if exc.code in {'COMMUNICATION_UNKNOWN','ENDPOINT_IDENTITY_MISMATCH','AUTHENTICATION_FAILED'}: raise
                        log_error = exc.code # Logs failing cannot erase independently queried Run evidence.
                    page = call(client.events, ecursor, 64)
                    # Global sequence gaps belonging to other Runs are not lost records.
                    for event in page:
                        ecursor = max(ecursor, event['project_sequence'])
                        if event['run_id'] == run['run_id']:
                            events.append({k: event.get(k) for k in ('project_sequence', 'type', 'observed_at')})
                with self.selection_lock:
                    if version != self.selection_version: continue
                self._publish({'connected': True, 'selection_version': version, 'observed_at': datetime.now().astimezone().isoformat(),
                               'endpoint': {k: client.endpoint[k] for k in ('project_id','project_instance_id','owner_id')},
                               'owner_process': {k:health['process'].get(k) for k in ('pid','creation_time_100ns')},
                               'receipt': receipt, 'run': run, 'gate': gate,
                               'validations': [{k:v.get(k) for k in ('validation_id','verdict','recorded_at')} for v in validations[-8:]],
                               'progress': list(progress), 'events': list(events),
                               'log_error': log_error, 'progress_source': progress_source,
                               'closeout': closeout, 'interruption': interruption, 'recovery': recovery,
                               'project_page': project_page,
                               'job_name': selection.get('job_name') if selection else None,
                               'progress_cursor': pcursor, 'event_cursor': ecursor})
            except InterruptedError:
                return
            except Exception as exc:
                self._publish({'connected': False, 'selection_version': version, 'code': exc.code if isinstance(exc, ExecutionError) else 'READ_FAILED'})
            self.stop.wait(0.3)


class ExecutionView:
    def __init__(self, app, connection, request_key, observer=None):
        self.app, self.observer = app, observer
        self.closed, self.last_update, self.last_view = False, '尚无成功读取', None
        self.project, self.connection = None, connection
        self.readers, self.run_items = [], {}
        self.lifecycle_threads=[];self.lifecycle_results=queue.Queue();self.lifecycle_generation=0
        self.lifecycle_busy=False
        self.next_page = self.selected_run_id = None
        app.title('AbqJobPilot Dev '+__version__+' · 独立执行服务')
        app._apply_icon(); app._set_initial_geometry(); app._configure_styles()
        app.columnconfigure(0, weight=1); app.rowconfigure(2, weight=1)
        header = ttk.Frame(app, padding=12); header.grid(row=0, column=0, sticky='ew')
        self.identity = tk.StringVar(value='连接显式隔离 Project…')
        ttk.Label(header, text='独立执行服务 / 显式隔离 Project', font=('Segoe UI', 14, 'bold')).pack(anchor='w')
        ttk.Label(header, textvariable=self.identity).pack(anchor='w')
        ttk.Label(header, text='只读查看 · 关闭窗口不停止服务 · 重新打开不提交、不批准、不恢复派发').pack(anchor='w')
        controls=ttk.Frame(header); controls.pack(fill='x',pady=(6,0))
        self.new_button=ttk.Button(controls,text='New Agent-first Project…',command=self.new_project)
        self.new_button.pack(side='left',padx=(0,6))
        self.choose_button=ttk.Button(controls,text='选择 Agent-first Project…',command=self.choose_project)
        self.choose_button.pack(side='left')
        ttk.Button(controls,text='重新连接',command=self.reconnect).pack(side='left',padx=6)
        ttk.Button(controls,text='指定连接材料…',command=self.choose_connection).pack(side='left')
        self.start_button=ttk.Button(controls,text='Start Service',command=lambda:self.lifecycle_action('start'))
        self.start_button.pack(side='left',padx=6)
        ttk.Button(controls,text='Disconnect',command=self.disconnect).pack(side='left')
        self.stop_button=ttk.Button(controls,text='Stop Service',command=self.stop_service)
        self.stop_button.pack(side='left',padx=6)
        ttk.Button(controls,text='Legacy 队列界面',command=self.legacy).pack(side='right')
        self.project_label=tk.StringVar(value='未选择 Project；不会自动启动服务或读取 Recent')
        ttk.Label(header,textvariable=self.project_label).pack(anchor='w')
        self.service_status=tk.StringVar(value='服务生命周期：尚未选择；启动/停止仅支持预配置 TEST_ONLY Project')
        ttk.Label(header,textvariable=self.service_status).pack(anchor='w')
        app.running_summary_var = tk.StringVar(value='CONNECTING')
        app.resource_line_var = tk.StringVar(value='每实验存储 1 槽')
        app._build_status_area(app)
        app.view_running_button.configure(text='只读', state='disabled', command=lambda: None)
        app.resource_button.configure(state='disabled', command=lambda: None)
        body = ttk.PanedWindow(app, orient='vertical'); body.grid(row=2, column=0, sticky='nsew', padx=12)
        listing=ttk.Frame(body);body.add(listing,weight=1)
        listing.columnconfigure(0,weight=1);listing.rowconfigure(1,weight=1)
        paging=ttk.Frame(listing);paging.grid(row=0,column=0,sticky='ew')
        ttk.Label(paging,text='Agent-first Runs · 每页最多32项 · 选择查看').pack(side='left')
        ttk.Button(paging,text='最新一页',command=lambda:self.page(0)).pack(side='right')
        self.older_button=ttk.Button(paging,text='更早一页',command=lambda:self.page(self.next_page),state='disabled')
        self.older_button.pack(side='right',padx=6)
        self.run_tree=ttk.Treeview(listing,columns=('run','job','stage'),show='headings',height=4)
        app._configure_tree(self.run_tree,{'run':'Run ID','job':'Job / 名称','stage':'执行阶段'},
                            {'run':340,'job':300,'stage':260})
        self.run_tree.grid(row=1,column=0,sticky='nsew')
        bar=ttk.Scrollbar(listing,orient='vertical',command=self.run_tree.yview)
        bar.grid(row=1,column=1,sticky='ns');self.run_tree.configure(yscrollcommand=bar.set)
        self.run_tree.bind('<<TreeviewSelect>>',self.select_run)
        states = ttk.Frame(body); body.add(states, weight=1)
        states.rowconfigure(0, weight=1); states.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(states, columns=('item','value'), show='headings', height=13)
        app._configure_tree(self.tree, {'item':'状态维度 / 历史证据', 'value':'当前读取值'}, {'item':240, 'value':900})
        self.tree.grid(row=0,column=0,sticky='nsew')
        app._attach_scrollbars(states,self.tree)
        app.live_source_var = tk.StringVar(value='TEST')
        app.live_follow_vars = {k: tk.BooleanVar(value=True) for k in ('solver','console')}
        app.live_origin_vars = {'solver':tk.StringVar(value='worker 自报进度（不是退出证明）'),
                               'console':tk.StringVar(value='持久化事件 · 最近 64 条')}
        app._build_live_logs(body)
        app.live_source_selector.configure(values=('TEST',),state='disabled')
        app.live_source_selector.unbind('<<ComboboxSelected>>')
        app.console_heading.configure(text='EVENT')
        app.live_solver_follow.configure(text='跟随'); app.live_console_follow.configure(text='跟随')
        app._build_footer()
        self.reader = Reader(connection, request_key) if connection is not None else None
        if self.reader:self.readers.append(self.reader)
        else:app.running_summary_var.set('DISCONNECTED · 请明确选择 Agent-first Project')
        app.protocol('WM_DELETE_WINDOW', app.destroy)
        self.timer = app.after(50, self._drain)

    def _drain(self):
        if self.closed: return
        try: value = self.reader.views.get_nowait() if self.reader else None
        except queue.Empty: value = None
        if value is not None: self._render(value)
        try:
            generation,operation,result=self.lifecycle_results.get_nowait()
            if generation==self.lifecycle_generation:
                self.lifecycle_busy=False
                self.service_status.set('服务 '+result.get('state','BLOCKED')+' · '+result.get('reason',''))
                if operation=='create' and result.get('state')=='CREATED':
                    self.attach_project(result['directory'])
                if result.get('project_name'):
                    self.project_label.set(result['project_name']+' · '+str(self.project)+' · Agent-first / format 1 / store 3')
                    self.identity.set('Project '+result['project_id']+'  |  instance '+result['project_instance_id'])
                if operation=='start' and result.get('state') in {'CONNECTED','STARTING'}:self.reconnect()
                if operation=='stop' and result.get('state')=='STOPPING':self.disconnect()
        except queue.Empty:pass
        self.timer = self.app.after(80, self._drain)

    def choose_project(self):
        path=filedialog.askdirectory(parent=self.app,title='选择 Agent-first Project（不会初始化或迁移）',mustexist=True)
        if path:self.attach_project(path)

    def new_project(self):
        if self.lifecycle_busy:return
        path=filedialog.asksaveasfilename(parent=self.app,title='指定新的 Project 目录名（必须尚不存在）',confirmoverwrite=True)
        if not path:return
        name=simpledialog.askstring('New Agent-first Project','Project 显示名称',parent=self.app)
        if name is None:return
        self.lifecycle_generation+=1;generation=self.lifecycle_generation
        self.lifecycle_busy=True;self.service_status.set('CREATING · 空 Project / PAUSED / 无执行授权')
        def work():
            try:
                from .product_project import create_project
                create_project(path,name)
                result={'state':'CREATED','directory':path}
            except Exception as exc:
                result={'state':'BLOCKED','reason':exc.code if isinstance(exc,ExecutionError) else 'PROJECT_CREATE_FAILED'}
            self.lifecycle_results.put((generation,'create',result))
        thread=threading.Thread(target=work,name='explicit-project-create')
        self.lifecycle_threads.append(thread);thread.start()

    def choose_connection(self):
        if not self.project:return
        path=filedialog.askopenfilename(parent=self.app,title='选择该实例的私有 connection.json',filetypes=[('JSON','*.json')])
        if path:self.attach_project(self.project,path)

    def attach_project(self, path, connection=None):
        if self.reader:self.reader.stop.set()
        self.project,self.connection=path,connection
        self.lifecycle_generation+=1;self.lifecycle_busy=False
        self.last_view=None;self.last_update='尚无成功读取';self.selected_run_id=None
        self.run_items={};self.next_page=None;self.older_button.configure(state='disabled')
        self.run_tree.delete(*self.run_tree.get_children());self.tree.delete(*self.tree.get_children())
        for box in self.app.live_log_texts.values():self.app._set_text(box,'',follow=True)
        self.identity.set('Project 身份待核验')
        self.project_label.set('已选择：'+str(path)+' · Agent-first（只读）')
        self.app.running_summary_var.set('CONNECTING · 正在核对所选 Project / owner')
        self.reader=Reader(connection,None,project=path);self.readers.append(self.reader)
        self.lifecycle_action('inspect')

    def lifecycle_action(self, operation):
        if not self.project or self.lifecycle_busy:return
        project,connection=self.project,self.connection
        generation=self.lifecycle_generation;self.lifecycle_busy=True
        owner=self.last_view['endpoint']['owner_id'] if self.last_view else None
        self.service_status.set({'start':'STARTING','stop':'STOPPING','inspect':'检查服务（只读）'}[operation])
        def work():
            try:
                from .service_lifecycle import ServiceLifecycleManager
                from .execution.models import identifier
                manager=ServiceLifecycleManager(project,connection)
                if operation=='inspect':
                    result=manager.inspect()
                    from .local_credentials import protected_project
                    if protected_project(manager.context):
                        from .product_project import validate_product
                        result['project_name']=validate_product(manager.context)['display_name']
                        result['project_id']=manager.context.project_id
                        result['project_instance_id']=manager.context.project_instance_id
                elif operation=='start':result=manager.start()
                else:
                    require(owner is not None,'ENDPOINT_IDENTITY_MISMATCH','Connect exact owner before stopping')
                    # Key is displayed/retained even on an uncertain response; never compensate by kill.
                    # Stable per owner across GUI restarts; a lost response must
                    # query/replay this operation, never create a new stop key.
                    key='gui_stop_'+owner
                    response=manager.stop(owner_id=owner,operation_key=key)
                    result={'state':'STOPPING','reason':response['receipt']['operation_id']+' / '+key}
            except Exception as exc:
                result={'state':'BLOCKED','reason':exc.code if isinstance(exc,ExecutionError) else 'LIFECYCLE_UNAVAILABLE'}
            self.lifecycle_results.put((generation,operation,result))
        thread=threading.Thread(target=work,name='explicit-service-lifecycle');self.lifecycle_threads.append(thread);thread.start()

    def stop_service(self):
        if self.project and messagebox.askyesno('停止空闲测试服务',
                '仅停止当前 Project 的空闲服务。需要独立操作者权限；活跃、UNKNOWN 或保留资源将拒绝。不会终止 Solver。',parent=self.app):
            self.lifecycle_action('stop')

    def disconnect(self):
        # Ignore a late lifecycle response for display only. An already issued
        # start/stop is not cancelled, repeated or compensated by this action.
        self.lifecycle_generation+=1;self.lifecycle_busy=False
        if self.reader:self.reader.stop.set()
        self.reader=None
        self._render({'connected':False,'code':'DISCONNECTED'})
        self.service_status.set('DISCONNECTED · 仅断开 GUI；服务状态请明确重新检查')

    def reconnect(self):
        if self.project:
            # Same explicit Project: retain selection/cache, but reauthenticate.
            # Project changes use attach_project and discard all prior data.
            previous=self.reader
            if previous:previous.stop.set()
            self.reader=Reader(self.connection,None,project=self.project)
            if previous:
                with previous.selection_lock:
                    self.reader.select(previous.selection)
                    self.reader.page(previous.before_row)
            elif self.selected_run_id in self.run_items:
                self.reader.select(self.run_items[self.selected_run_id])
            self.readers.append(self.reader)
            self._render({'connected':False,'code':'RECONNECTING'})

    def page(self,cursor):
        if self.reader and self.project and cursor is not None:self.reader.page(cursor)

    def select_run(self,event=None):
        ids=self.run_tree.selection()
        if not ids or ids[0] not in self.run_items or ids[0]==self.selected_run_id:return
        self.selected_run_id=ids[0]
        self.reader.select(self.run_items[ids[0]])

    def legacy(self):
        self.app.legacy_requested=True
        self.app.destroy()

    def _render(self, value):
        app = self.app
        if not value['connected']:
            if not self.lifecycle_busy and self.service_status.get().startswith('服务 CONNECTED'):
                self.service_status.set('DISCONNECTED · '+value['code']+' · 最后成功读取 '+self.last_update)
            app.running_summary_var.set('连接中断 DISCONNECTED / 缓存不是实时状态 · ' + value['code'] + ' · ' +
                                        CONNECTION_REASONS.get(value['code'],'只读连接失败；不会修改任务或自动修复'))
            app.status_light.itemconfigure(app.status_light_id, fill='#dc2626')
            app.footer_mode_var.set('最后成功读取：' + self.last_update + ' · 不推断任务失败或已停止')
        else:
            self.last_view, self.last_update = value, value['observed_at']
            ep, run, receipt = value['endpoint'], value['run'], value['receipt']
            if not self.lifecycle_busy and self.service_status.get().startswith('DISCONNECTED'):
                self.service_status.set('服务 CONNECTED · '+ep['owner_id'])
            page=value.get('project_page')
            if page:
                self.run_items={r['run_id']:r for r in page['runs']}
                for iid in self.run_tree.get_children():
                    if iid not in self.run_items:self.run_tree.delete(iid)
                for idx,r in enumerate(page['runs']):
                    vals=(r['run_id'],r.get('job_name') or r['job_id'],r['execution']+' / '+str(r.get('execution_phase') or ''))
                    if self.run_tree.exists(r['run_id']):self.run_tree.item(r['run_id'],values=vals)
                    else:self.run_tree.insert('','end',iid=r['run_id'],values=vals)
                    self.run_tree.move(r['run_id'],'',idx)
                self.next_page=page['next_before_row']
                self.older_button.configure(state='normal' if self.next_page is not None else 'disabled')
            self.identity.set('Project ' + ep['project_id'] + '  |  instance ' + ep['project_instance_id'])
            app.running_summary_var.set('已连接 · ' + ((run['execution'] + ' / ' + run.get('execution_phase','')) if run else ('请选择 Run' if page else '尚无该请求回执')) +
                                        ' · 派发 ' + str(value['gate']['state']))
            app.status_light.itemconfigure(app.status_light_id, fill='#16a34a')
            rows = [('Owner', ep['owner_id']), ('Run ID',run['run_id'] if run else '未提交'),
                    ('原始接收回执',receipt['request_id'] if receipt else '未记录'),
                    ('请求 / 接受时间',(receipt['idempotency_key']+' / '+str(receipt['accepted_at'])) if receipt else '未记录')]
            if value.get('owner_process'):
                rows += [('Owner PID / 创建身份',str(value['owner_process']))]
            if run:
                app.live_source_var.set('TEST')
                app.live_origin_vars['solver'].set('worker 自报进度（不是退出证明）')
                rows += [('Job ID',run['job_id']),('Job 名称',value.get('job_name') or '未记录（以 Job ID 关联）'),('Plan ID',run['plan_id'])]
                rows += [(label,str(run.get(key,'未记录'))) for label,key in (
                    ('Backend','backend_id'),('排队','queue_state'),('执行阶段','execution'),
                    ('Backend 结果','backend_outcome'),('最后记录的进程观察','process_observation'),
                    ('OS 退出验证','exit_verification'),('Artifact 独立验证','artifact_validation'),
                    ('Solver 结论','solver_conclusion'))]
                if run['backend_id'] == 'abaqus-standard-axial-2024-v1':
                    app.live_source_var.set('STANDARD')
                    app.live_origin_vars['solver'].set('有界文本摘要 / 不是完整进程退出证明')
                    rows += [(label,str(run.get(key,'未记录'))) for label,key in (
                        ('当前执行阶段','execution_phase'),
                        ('创建状态','launch_state'),('完整成员集合','member_completeness'),('整体退出','overall_exit'),
                        ('DAT 数值验证','numerical_validation'),('ODB 内容验证','odb_content_validation'),
                        ('结构化问题','standard_error'),('结果读取原因','result_reason'))]
                rows += [('对账需求',run.get('reconciliation_requirement','UNKNOWN')
                          if run.get('owner_id') != ep['owner_id'] else run['reconciliation'])]
                rows += [('已记录 OS 退出', '; '.join(str(e['role'])+'='+str(e['exit_code']) for e in run.get('process_exits',[])) or '尚无退出证据')]
                if run.get('managed_scope'):
                    scope=run['managed_scope']
                    rows += [('受管进程范围',scope.get('scope_id','未记录')),
                             ('范围最后活动数',str(scope.get('active_processes','未记录'))+'（历史 OS 查询）'),
                             ('范围收尾',run.get('managed_completion','NOT_CONFIRMED')),
                             ('范围保证','该 Job 的继承后代；不是系统所有进程或 Solver 结论')]
                if run.get('batch_position'):
                    rows += [('固定顺序位置',run['batch_position']),
                             ('批次观察截止（UTC秒）',str(run.get('batch_observation_not_after','未记录')))]
                rows += [('独立验证记录（历史）',json.dumps(value['validations'],ensure_ascii=False))]
            rows += [('派发门',str(value['gate']['state']))]
            if page:rows += [('逻辑槽占用',str(page['slot_run_id'])),('Project 列表读取时间',str(page['read_at']))]
            assessment = value.get('closeout')
            if assessment:
                if assessment.get('unavailable'): rows += [('收尾预览',assessment['unavailable'])]
                else:
                    rows += [('逻辑槽占用',str(assessment['resources']['slot_run_id'])),
                             ('工程/输出保留',assessment['resources']['retention']),
                             ('行政处置（不改退出证据）',str(assessment['historical_facts'].get('administrative_closeout'))),
                             ('收尾预览版本',assessment['preview_digest']),
                             ('可审阅处置',', '.join(a['action'] for a in assessment['actions'] if a['eligible']) or '无；检查前置条件'),
                             ('仍未知',', '.join(assessment['unknowns']))]
            if value.get('log_error'): rows += [('日志读取（保留其他状态）',value['log_error'])]
            y, x = self.tree.yview(), self.tree.xview()
            self.tree.delete(*self.tree.get_children())
            for row in rows: self.tree.insert('', 'end', values=row)
            if y: self.tree.yview_moveto(y[0])
            if x: self.tree.xview_moveto(x[0])
            for side, records in (('solver',value['progress']),('console',value['events'])):
                app._set_text(app.live_log_texts[side], '\n'.join(json.dumps(r,ensure_ascii=False) for r in records),
                              follow=app.live_follow_vars[side].get())
            app.footer_mode_var.set('最后成功读取：' + self.last_update + ' · 历史观察；多次有界公共查询，不是原子快照')
        if self.observer:
            # Test telemetry is derived from rendered widgets, not a second reader.
            self.observer({'connected':value['connected'], 'last_update':self.last_update,
                           'status':app.running_summary_var.get(),
                           'rows':[list(self.tree.item(i,'values')) for i in self.tree.get_children()],
                           'progress_text':app.live_log_texts['solver'].get('1.0','end'),
                           'event_text':app.live_log_texts['console'].get('1.0','end'),
                           'run_list':[list(self.run_tree.item(i,'values')) for i in self.run_tree.get_children()]})

    def close(self):
        if self.closed: return
        self.closed = True
        for reader in self.readers:reader.stop.set()
        self.app.after_cancel(self.timer)
        # Non-daemon reader finishes its one bounded outstanding request. No
        # owner operation, process stop, credential deletion or lock release.
