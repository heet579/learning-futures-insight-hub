"""Non-blocking Gemini insights view with a local baseline and session cache."""
import tkinter as tk
from tkinter import ttk, messagebox

from src.ai.insights import insight_evidence, local_insights, render_insights
from src.ui.theme import BG, INK
from src.ui.wording import service_message


class InsightsUI:
    def build_insights(self, parent):
        self.insights_cache = {}
        self.insights_poll = None
        self.insights_consent = tk.BooleanVar(value=False)
        actions = tk.Frame(parent, bg=BG)
        actions.pack(fill='x', padx=12, pady=(12, 4))
        self.insights_button = self.action(actions, 'Generate insights', self.generate_insights, True)
        self.insights_button.pack(side='left')
        self.action(actions, 'Show local insights', self.show_local_insights).pack(side='left', padx=8)
        self.insights_consent_check = ttk.Checkbutton(
            parent, text='Allow cloud processing of calculated metrics and theme counts',
            variable=self.insights_consent)
        self.insights_consent_check.pack(anchor='w', padx=12)
        tk.Label(parent, bg=BG, fg=INK, justify='left', text='Summaries are sent to an external service; raw comments and learner identifiers stay local.\n'
                  'Free-tier limits apply, and submitted summaries may be used to improve the service.',
                  wraplength=780).pack(anchor='w', padx=16, pady=(0, 8))
        self.insights_text = self.text(parent)
        self.insights_text.pack(fill='both', expand=True, padx=12, pady=(0, 12))
        self.show(self.insights_text, 'Import survey data to see insights and suggested next steps.')

    def show_local_insights(self):
        if self.context and not self.busy:
            self.render(self.insights_text, local_insights(self.context))

    def generate_insights(self):
        import json
        from src.ai.gemini_provider import GeminiAIProvider
        if not self.context or self.busy:
            return
        if not self.insights_consent.get():
            messagebox.showinfo('Cloud processing', 'Tick the consent checkbox to send calculated summaries to the external service.', parent=self.root)
            return
        try:
            provider = GeminiAIProvider()
        except ValueError as exc:
            messagebox.showinfo('Service setup', service_message(exc), parent=self.root)
            return
        key = json.dumps([provider.model, insight_evidence(self.context)], sort_keys=True)
        if key in self.insights_cache:
            self.render(self.insights_text, self.insights_cache[key])
            self.status.set('Insights restored from this session.')
            return
        context = self.context
        self.busy = True
        self.status.set('Generating insights from calculated evidence...')
        self.progress.start(12)
        self.sync_controls()
        future = self.pool.submit(provider.insights, context)

        def finish():
            if not future.done():
                self.insights_poll = self.root.after(80, finish)
                return
            self.insights_poll = None
            self.busy = False
            self.progress.stop()
            self.progress.configure(value=0)
            try:
                content = render_insights(future.result(), context, provider.model)
            except Exception as exc:
                self.render(self.insights_text, local_insights(context))
                self.status.set('Cloud insights unavailable; showing local analysis.')
                messagebox.showerror('Insights unavailable', service_message(exc), parent=self.root)
            else:
                self.insights_cache[key] = content
                self.render(self.insights_text, content)
                self.status.set('Insights ready. Review interpretations against the supporting evidence.')
            self.sync_controls()

        self.insights_poll = self.root.after(80, finish)
