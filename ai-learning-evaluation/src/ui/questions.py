"""Question answering with explicit provider labels and background API requests."""
import json

from src.ai.insights import insight_evidence
from src.privacy.pii_masker import mask_text
from src.ui.wording import service_message


class QuestionsUI:
    def ask(self, question=None):
        if self.busy:
            return
        if not self.context:
            self.show(self.answer, 'Load a dataset first, then choose a question.')
            return
        text = question if question is not None else self.question.get().strip()
        if question is not None:
            self.question.delete(0, 'end')
            self.question.insert(0, question)
        if not text.strip() or len(text) > 2000:
            self.show(self.answer, 'Enter a question between 1 and 2,000 characters.')
            return
        context = self.context
        scope = f'\n\n## Analysis scope\n{context.course_name} | {context.metrics["response_count"]:,} responses'
        from src.ai.gemini_provider import GeminiAIProvider
        try:
            provider = GeminiAIProvider()
        except ValueError as exc:
            self.show(self.answer, 'Question answering is not configured. Contact your workspace administrator.')
            return
        facts = insight_evidence(context)
        key = json.dumps([provider.model, mask_text(text.strip()), facts], sort_keys=True)

        def display(result):
            evidence = '\n'.join(f'- {facts[ref]}' for ref in result['evidence_ids'])
            content = f'## Answer\n{result["answer"]}'
            if evidence:
                content += f'\n\n## Supporting calculated evidence\n{evidence}'
            content += f'{scope}\n\nReview interpretations against the supporting evidence.'
            self.render(self.answer, content)

        if key in self.question_cache:
            display(self.question_cache[key])
            self.status.set('Answer restored from this session.')
            return
        self.busy = True
        self.show(self.answer, 'Analysing your question and the selected survey evidence...')
        self.status.set('Preparing an answer from the selected data...')
        self.progress.start(12)
        self.sync_controls()
        future = self.pool.submit(provider.answer_question, context, text)

        def finish():
            if not future.done():
                self.question_poll = self.root.after(80, finish)
                return
            self.question_poll = None
            self.busy = False
            self.progress.stop()
            self.progress.configure(value=0)
            try:
                result = future.result()
            except Exception as exc:
                self.show(self.answer, f'Could not answer this question.\n\n{service_message(exc)}\n\nPlease try again later.')
                self.status.set('Request failed. Your survey data is unchanged.')
            else:
                self.question_cache[key] = result
                display(result)
                self.status.set('Answer ready, based on the selected survey evidence.')
            self.sync_controls()

        self.question_poll = self.root.after(80, finish)
