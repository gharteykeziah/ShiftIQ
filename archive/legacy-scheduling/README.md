# Legacy scheduling code

`shift_engine.py` and `shift_planner_ui.py` are the first-generation
scheduling backend and its standalone tkinter UI. Both were superseded by
`schedule_core.py` (imported by `page_schedule.py`, the live schedule tab in
the app) and are not imported anywhere in the current application.

They're kept here for reference rather than deleted outright, since
`shift_planner_ui.py` is still runnable as a standalone tool against the same
`schedule_core.py` tables (`schedule_jobs` / `schedule_shifts`) if anyone needs it.

Do not import either file in new code.
