"""Connect-only adapter for the existing Dev Tk application.

No store, owner, authority, legacy Runtime or execution imports. A polling thread
does bounded public reads; Tk receives a latest-only view. Views are successive
observations, not an atomic database/process snapshot.
"""
from collections import deque
from datetime import datetime
import json
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import ttk

from . import __version__
from .execution.client import FakeClient
from .execution.models import ExecutionError, fields, require, text
from .execution.paths import local_path, no_reparse


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
    def __init__(self, connection, request_key):
        text(request_key)
        self.connection, self.key = connection, request_key
        self.stop = threading.Event()
        self.views = queue.Queue(maxsize=1)
        self.thread = threading.Thread(target=self._loop, name='execution-public-reader')
        self.thread.start()

    def _publish(self, value):
        try: self.views.get_nowait()
        except queue.Empty: pass
        self.views.put_nowait(value)

    def _loop(self):
        progress, events = deque(maxlen=128), deque(maxlen=64)
        pcursor = ecursor = 0
        owner = None
        project_binding = None
        while not self.stop.is_set():
            try:
                client = read_connection(self.connection)
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
                health = call(client.health)
                try: receipt = call(client.receipt, self.key)
                except ExecutionError as exc:
                    if exc.code != 'NOT_FOUND': raise
                    receipt = None
                gate = call(client.dispatch_gate)
                run = call(client.run, receipt['run_id']) if receipt else None
                validations = call(client.validations, run['run_id']) if run else []
                closeout = None
                if run and run.get('backend_id') == 'abaqus-standard-axial-2024-v1' and 'preview_closeout' in health.get('operations',[]):
                    try: closeout = call(client.preview_closeout, run['run_id'])
                    except ExecutionError as exc:
                        if exc.code in {'COMMUNICATION_UNKNOWN','ENDPOINT_IDENTITY_MISMATCH','AUTHENTICATION_FAILED'}: raise
                        closeout = {'unavailable':exc.code}
                log_error = None
                if run:
                    try:
                        page = call(client.progress, run['run_id'], pcursor, 64)
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
                self._publish({'connected': True, 'observed_at': datetime.now().astimezone().isoformat(),
                               'endpoint': {k: client.endpoint[k] for k in ('project_id','project_instance_id','owner_id')},
                               'receipt': receipt, 'run': run, 'gate': gate,
                               'validations': [{k:v.get(k) for k in ('validation_id','verdict','recorded_at')} for v in validations[-8:]],
                               'progress': list(progress), 'events': list(events),
                               'log_error': log_error,
                               'closeout': closeout,
                               'progress_cursor': pcursor, 'event_cursor': ecursor})
            except InterruptedError:
                return
            except Exception as exc:
                self._publish({'connected': False, 'code': exc.code if isinstance(exc, ExecutionError) else 'READ_FAILED'})
            self.stop.wait(0.3)


class ExecutionView:
    def __init__(self, app, connection, request_key, observer=None):
        self.app, self.observer = app, observer
        self.closed, self.last_update, self.last_view = False, '尚无成功读取', None
        app.title('AbqJobPilot Dev '+__version__+' · 独立执行服务')
        app._apply_icon(); app._set_initial_geometry(); app._configure_styles()
        app.columnconfigure(0, weight=1); app.rowconfigure(2, weight=1)
        header = ttk.Frame(app, padding=12); header.grid(row=0, column=0, sticky='ew')
        self.identity = tk.StringVar(value='连接显式隔离 Project…')
        ttk.Label(header, text='独立执行服务 / 显式隔离 Project', font=('Segoe UI', 14, 'bold')).pack(anchor='w')
        ttk.Label(header, textvariable=self.identity).pack(anchor='w')
        ttk.Label(header, text='只读查看 · 关闭窗口不停止服务 · 重新打开不提交、不批准、不恢复派发').pack(anchor='w')
        app.running_summary_var = tk.StringVar(value='CONNECTING')
        app.resource_line_var = tk.StringVar(value='每实验存储 1 槽')
        app._build_status_area(app)
        app.view_running_button.configure(text='只读', state='disabled', command=lambda: None)
        app.resource_button.configure(state='disabled', command=lambda: None)
        body = ttk.PanedWindow(app, orient='vertical'); body.grid(row=2, column=0, sticky='nsew', padx=12)
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
        self.reader = Reader(connection, request_key)
        app.protocol('WM_DELETE_WINDOW', app.destroy)
        self.timer = app.after(50, self._drain)

    def _drain(self):
        if self.closed: return
        try: value = self.reader.views.get_nowait()
        except queue.Empty: value = None
        if value is not None: self._render(value)
        self.timer = self.app.after(80, self._drain)

    def _render(self, value):
        app = self.app
        if not value['connected']:
            app.running_summary_var.set('连接中断 / 缓存不是实时状态 · ' + value['code'])
            app.status_light.itemconfigure(app.status_light_id, fill='#dc2626')
            app.footer_mode_var.set('最后成功读取：' + self.last_update + ' · 不推断任务失败或已停止')
        else:
            self.last_view, self.last_update = value, value['observed_at']
            ep, run, receipt = value['endpoint'], value['run'], value['receipt']
            self.identity.set('Project ' + ep['project_id'] + '  |  instance ' + ep['project_instance_id'])
            app.running_summary_var.set('已连接 · ' + ((run['execution'] + ' / ' + run.get('execution_phase','')) if run else '尚无该请求回执') +
                                        ' · 派发 ' + str(value['gate']['state']))
            app.status_light.itemconfigure(app.status_light_id, fill='#16a34a')
            rows = [('Owner', ep['owner_id']), ('Run ID',run['run_id'] if run else '未提交'),
                    ('原始接收回执',receipt['request_id'] if receipt else '未记录'),
                    ('请求 / 接受时间',(receipt['idempotency_key']+' / '+str(receipt['accepted_at'])) if receipt else '未记录')]
            if run:
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
                rows += [('独立验证记录（历史）',json.dumps(value['validations'],ensure_ascii=False))]
            rows += [('派发门',str(value['gate']['state']))]
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
                           'event_text':app.live_log_texts['console'].get('1.0','end')})

    def close(self):
        if self.closed: return
        self.closed = True
        self.reader.stop.set()
        self.app.after_cancel(self.timer)
        # Non-daemon reader finishes its one bounded outstanding request. No
        # owner operation, process stop, credential deletion or lock release.
