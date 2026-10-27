"""The CLEAR review questions in the desktop app (the same questions as the browser app)."""
from __future__ import annotations

import time
import tkinter as tk
from tkinter import messagebox, ttk

from src.review import clear


def ask_clear(parent, state, context):
    """Show the reviewer's questions. Returns the answers (for repository.transition) or None if cancelled."""
    material = clear.examine(state, context)
    started = time.monotonic()
    window = tk.Toplevel(parent)
    window.title('Your judgement')
    window.transient(parent)
    window.geometry('760x680')
    window.minsize(560, 420)
    result = {}

    canvas = tk.Canvas(window, highlightthickness=0, background='white')
    scroll = ttk.Scrollbar(window, orient='vertical', command=canvas.yview)
    body = tk.Frame(canvas, background='white', padx=18, pady=14)
    body.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
    holder = canvas.create_window((0, 0), window=body, anchor='nw')
    canvas.bind('<Configure>', lambda e: canvas.itemconfigure(holder, width=e.width))
    canvas.configure(yscrollcommand=scroll.set)
    canvas.pack(side='left', fill='both', expand=True)
    scroll.pack(side='right', fill='y')

    wrap = 680
    level = material['level']
    tk.Label(body, text='Your judgement', font=('Segoe UI', 15, 'bold'), fg='#151054', bg='white').pack(anchor='w')
    tk.Label(body, text=(f"{level['label']} review. " + ' '.join(level['reasons']) +
                         ' The app has already checked every fact. Your answers go into the report and the audit record.'),
             wraplength=wrap, justify='left', fg='#6B6382', bg='white').pack(anchor='w', pady=(2, 10))

    choices, texts = {}, {}

    def question(n, q):
        frame = tk.Frame(body, bg='white', highlightbackground='#E4DDF2', highlightthickness=1, padx=12, pady=10)
        frame.pack(fill='x', pady=6)
        tk.Label(frame, text=f"{n}. {q['title']}", font=('Segoe UI', 11, 'bold'), fg='#151054', bg='white').pack(anchor='w')
        tk.Label(frame, text=q['prompt'], wraplength=wrap - 30, justify='left', fg='#6B6382', bg='white').pack(anchor='w', pady=(0, 6))
        return frame

    def radio(frame, name, options):
        var = tk.StringVar(value='')
        row = tk.Frame(frame, bg='white')
        row.pack(anchor='w', pady=(4, 4))
        for value, label in options.items():
            ttk.Radiobutton(row, text=label, value=value, variable=var).pack(side='left', padx=(0, 14))
        choices[name] = var

    def text(frame, name, label, initial=''):
        tk.Label(frame, text=label, bg='white', fg='#1E1631').pack(anchor='w')
        box = tk.Text(frame, height=3, wrap='word', relief='solid', borderwidth=1)
        box.insert('1.0', initial)
        box.pack(fill='x', pady=(2, 4))
        texts[name] = box

    for n, q in enumerate(material['questions'], 1):
        frame = question(n, q)
        if q['id'] == 'faithful':
            for c in material['comments']:
                tk.Label(frame, text=f"“{c['text']}”", wraplength=wrap - 50, justify='left', bg='#EFE8FB',
                         fg='#1E1631', font=('Segoe UI', 9, 'italic'), padx=8, pady=4).pack(anchor='w', fill='x', pady=2)
            radio(frame, 'faithful', q['choices'])
            text(frame, 'faithful_note', 'If Partly or No, what does the report miss?')
        elif q['id'] == 'balanced':
            tk.Label(frame, text='The report says: ' + material['claim'], wraplength=wrap - 30, justify='left',
                     bg='#E6F3EC', padx=8, pady=4).pack(anchor='w', fill='x', pady=2)
            tk.Label(frame, text='But the data also shows: ' + material['counter']['text'], wraplength=wrap - 30,
                     justify='left', bg='#FCF0DC', padx=8, pady=4).pack(anchor='w', fill='x', pady=2)
            radio(frame, 'balanced', q['choices'])
            text(frame, 'caveat', 'Caveat to add (used only if you choose "Add a caveat")', material['counter']['caveat'])
        elif q['id'] == 'owned':
            for r in material['recommendations'][:4]:
                tk.Label(frame, text='• ' + r, wraplength=wrap - 30, justify='left', bg='white', fg='#6B6382').pack(anchor='w')
            text(frame, 'owned', 'Your priority, in your own words')
        elif q['id'] == 'fair':
            radio(frame, 'fair', q['choices'])
            text(frame, 'fairness_note', 'Fairness note (if Yes)')
        elif q['id'] == 'fit':
            radio(frame, 'fit', q['choices'])
            text(frame, 'fit_note', 'If No, what should the author change?')

    def submit():
        answers = {name: var.get() for name, var in choices.items()}
        answers.update({name: box.get('1.0', 'end-1c').strip() for name, box in texts.items()})
        if answers.get('balanced') != 'caveat':
            answers['caveat'] = ''
        answers['seconds'] = time.monotonic() - started
        try:
            clear.validate(state, context, answers)
        except ValueError as exc:
            messagebox.showinfo('Almost there', str(exc), parent=window)
            return
        result['answers'] = answers
        window.destroy()

    buttons = tk.Frame(body, bg='white')
    buttons.pack(fill='x', pady=(10, 4))
    ttk.Button(buttons, text='Cancel', command=window.destroy).pack(side='right')
    ttk.Button(buttons, text='Approve report', command=submit).pack(side='right', padx=8)
    tk.Label(body, text='Answering "No" or "Partly" to the first question, or "No" to the last, sends the report back '
                        'to the author with your note.', wraplength=wrap, justify='left', fg='#6B6382', bg='white').pack(anchor='w')
    window.grab_set()
    parent.wait_window(window)
    return result.get('answers')
