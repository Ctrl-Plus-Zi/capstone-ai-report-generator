from __future__ import annotations

import json
import textwrap
from typing import List


def create_final_report_compose_agent(llm):

    def compose_report_node(state):
        request_context = state.get("request_context", {})
        analysis_outline = state.get("analysis_outline", "")
        analysis_findings = state.get("analysis_findings", "")
        research_notes = state.get("research_notes", "")
        messages: List = list(state.get("messages", []))

        prompt = textwrap.dedent(
            """
            You are responsible for drafting the final business report. Use the available analysis to prepare a
            Markdown document with clearly separated sections (Executive Summary, Key Insights, Recommendations,
            Next Steps).

            Request context:
            {request_context}

            Analysis outline:
            {analysis_outline}

            Analysis findings:
            {analysis_findings}

            Additional research notes:
            {research_notes}
            """
        ).format(
            request_context=json.dumps(request_context, ensure_ascii=False, indent=2),
            analysis_outline=analysis_outline,
            analysis_findings=analysis_findings,
            research_notes=research_notes,
        ).strip()

        response = llm.invoke(prompt)
        messages.append(response)
        final_report = response.content.strip() if response else "Report drafting is pending tool integration."

        return {
            "messages": messages,
            "final_report": final_report,
            "compose_prompt": prompt,
        }

    return compose_report_node
