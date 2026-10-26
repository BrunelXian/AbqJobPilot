"""Native widget checks; no service, no process creation, isolated preferences."""
import json
import queue
import tkinter as tk
from test_native_workspace import desktop
from test_native_visual import hwnd
from cockpit_capture import capture


def test_cockpit_layout_and_log_controls(desktop,tmp_path):
    app,w=desktop
    assert not w.nav
    measures=[]
    for width,height in [(1600,900),(1366,768)]:
        app.geometry(f'{width}x{height}+0+0');app.update();w.restore_layout(default=True);app.update()
        capture(hwnd(app),tmp_path/f'empty_{width}.png')
        assert w.language_box.winfo_rootx()+w.language_box.winfo_width()<=app.winfo_rootx()+width
        assert w.logs.winfo_height()>160
        w.pane.sashpos(0,300);w.logs.sashpos(0,400);app.update()
        assert abs(w.pane.sashpos(0)-300)<5
        for section in w.command_keys:
            w.show_command(section);app.update();assert w.command_panels[section].winfo_ismapped()
            assert w.drawer.winfo_width()==440
        w.drawer.grid_remove()
        for name,box in w.log_widgets.items():
            box.configure(state='normal');box.insert('end',('\n'+('long-line-'*70))*180);box.configure(state='disabled')
            box.xview_moveto(.5);box.yview_moveto(.2);app.update();assert box.xview()[0]>0
            box.event_generate('<MouseWheel>',delta=120);app.update();assert not w.follow[name].get()
        measures.append({'size':[width,height],'logs_height':w.logs.winfo_height(),'tk_scaling':app.tk.call('tk','scaling')})
    (tmp_path/'LAYOUT.json').write_text(json.dumps(measures),encoding='utf-8')


def test_obsolete_selection_snapshot_is_discarded(desktop):
    app,w=desktop
    w.selected_run_id='new'
    before=w.current_summary.get()
    w._render({'connected':True,'run':{'run_id':'old'}})
    assert w.current_summary.get()==before and w.last_view is None


def test_sort_filter_and_results_selection_without_side_effects(desktop):
    app,w=desktop
    w.run_items={rid:{'run_id':rid,'job_id':job,'execution':state} for rid,job,state in [('a','Zulu','FINISHED'),('b','Alpha','UNKNOWN')]}
    w.refresh_tables();assert w.queue_tree.get_children()==('b','a')
    w.sort_table(w.queue_tree,0);assert w.queue_tree.get_children()==('a','b')
    w.filters[w.queue_tree].set('Alpha');assert w.queue_tree.get_children()==('b',)
    w.results_tree.selection_set('a');w.results_tree.event_generate('<<TreeviewSelect>>');app.update()
    assert w.selected_run_id=='a' and w.reader is None and w.lifecycle_threads==[]
