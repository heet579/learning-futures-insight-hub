"""Non-blocking Gemini insights view with a local baseline and session cache."""
import tkinter as tk
from tkinter import messagebox

from src.ai.insights import insight_evidence, local_insights, render_insights
from src.ui.theme import BG
from src.ui.wording import service_message


class InsightsUI:
    def build_insights(self, parent):
        self.insights_cache = {}
        self.insights_poll = None
        actions = tk.Frame(parent, bg=BG)
        actions.pack(fill='x', padx=12, pady=(12, 4))
        self.insights_button = self.action(actions, 'Get insights', self.generate_insights, True)
        self.insights_button.pack(side='left')
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
        self.status.set('Preparing insights from calculated evidence...')
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
                self.status.set('Insights unavailable; showing the calculated overview. Try again later.')
                messagebox.showerror('Insights unavailable', service_message(exc), parent=self.root)
            else:
                self.insights_cache[key] = content
                self.render(self.insights_text, content)
                self.status.set('Insights ready. Review interpretations against the supporting evidence.')
            self.sync_controls()

        self.insights_poll = self.root.after(80, finish)
