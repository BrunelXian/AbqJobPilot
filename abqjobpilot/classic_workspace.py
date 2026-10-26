"""Embed the existing Classic widgets/controller without another Tk or mainloop.

Imported only after an explicit Classic selection. No default Runtime or Recent
selection is used. Navigation keeps this instance alive.
"""
import tkinter as tk
from tkinter import ttk
from .gui_app import AbqJobPilotApp, _load_legacy


class ClassicPane(ttk.Frame, AbqJobPilotApp):
    def __init__(self, parent, project, shell):
        ttk.Frame.__init__(self,parent)
        self.shell=shell
        _load_legacy()
        from . import config
        # Require existing complete Classic runtime before the original UI reads it.
        for name in ('queue.json','live_status.json'):
            if not (project.runtime_dir/name).is_file():raise ValueError('Incomplete Classic runtime')
        config.use_runtime_dir(project.runtime_dir)
        self._init_classic()
        self.project_manager.current=project
        self.lang='zh' if shell.locale=='zh-CN' else 'en'
        self._apply_language();self._update_project_label()
        self.queue_tree.column('status',width=220)
        self.results_tree.column('status',width=220)

    def title(self,*args): pass
    def _apply_icon(self): pass
    def _set_initial_geometry(self): pass

    def configure(self,cnf=None,**kwargs):
        # Menus belong to the one toplevel, and are exposed only on Classic.
        menu=kwargs.pop('menu',None);kwargs.pop('background',None)
        if menu is not None:self.menu_bar=menu
        if kwargs or cnf is not None:return ttk.Frame.configure(self,cnf,**kwargs)
    config=configure

    def _read_gpu_text(self):
        # No external nvidia-smi launch as a side effect of entering a page.
        return '—'

    def _build_menus(self):
        super()._build_menus()
        help_menu=self.nametowidget(self.menu_bar.entrycget(self.menu_bar.index('end'),'menu'))
        help_menu.entryconfigure(help_menu.index('end'),command=self.shell.request_close)

    def _fill_project_menu(self,menu):
        super()._fill_project_menu(menu)
        menu.entryconfigure(2,label=self.shell.t('executionWorkspace'),command=lambda:self.shell.navigate('runs'))

    def toggle_language(self):
        self.shell.change_language('en' if self.shell.locale=='zh-CN' else 'zh-CN')

    def close_project(self):
        # Do not fall back to a hidden default Runtime. Retain the scoped Classic
        # controller while the user switches back to the service workspace.
        self.shell.navigate('runs')

    def open_project(self,path):
        if not self._can_switch_project():return
        from .project.manager import load_project_info
        project=load_project_info(path)
        for name in ('queue.json','live_status.json'):
            if not (project.runtime_dir/name).is_file():raise ValueError('Incomplete Classic runtime')
        self._activate_project(project)

    def close_callbacks(self):
        for name in ('_poll_after_id','_selection_restore_after_id'):
            timer=getattr(self,name,None)
            if timer:
                try:self.after_cancel(timer)
                except tk.TclError:pass
                setattr(self,name,None)
        if getattr(self,'details_window',None):self.details_window.destroy()

    def destroy(self):
        self.close_callbacks();ttk.Frame.destroy(self)
