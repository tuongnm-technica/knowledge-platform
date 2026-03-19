import structlog
from services.llm_service import LLMService

log = structlog.get_logger()

REVIEWER_SYSTEM_PROMPT = """You are an expert Senior Business Analyst Reviewer.
Your task is to review the drafted document against the provided User Request and Context.
Look for:
1. Missing critical information.
2. Logical inconsistencies or contradictions.
3. Poor formatting or unclear language.
4. Deviations from the specified Project Memory context.

Output your review as a concise list of actionable feedback points.
If the draft is excellent and requires no changes, output exactly: "NO CHANGES NEEDED."
"""

class DocOrchestrator:
    def __init__(self, llm: LLMService = None):
        self.llm = llm or LLMService()

    async def generate_document_pipeline(self, system: str, user: str, max_tokens: int = 1800) -> str:
        """
        Executes a 3-step reasoning pipeline: Draft -> Review -> Refine.
        """
        log.info("doc_pipeline.start", step="drafting")
        
        # Step 1: Writer Agent creates the initial draft
        draft_content = await self.llm.chat(system=system, user=user, max_tokens=max_tokens)
        if not draft_content or len(draft_content.strip()) < 50:
            log.warning("doc_pipeline.draft_failed", reason="empty or too short")
            return draft_content

        # Step 2: Reviewer Agent critiques the draft
        log.info("doc_pipeline.step", step="reviewing")
        review_user_prompt = f"""
ORIGINAL USER REQUEST & CONTEXT:
{user}

DRAFTED DOCUMENT:
=========================================
{draft_content}
=========================================

Please review the document based on your system instructions. Provide actionable feedback.
"""
        feedback = await self.llm.chat(system=REVIEWER_SYSTEM_PROMPT, user=review_user_prompt, max_tokens=600)
        feedback_clean = feedback.strip().lower()

        if "no changes needed" in feedback_clean or len(feedback_clean) < 20:
            log.info("doc_pipeline.skip_refine", reason="no feedback or approved")
            return draft_content

        # Step 3: Editor Agent incorporates feedback to create the final draft
        log.info("doc_pipeline.step", step="refining")
        editor_user_prompt = f"""
ORIGINAL SYSTEM REQUIREMENTS AND MEMORY APPLY TO THIS REVISION.

ORIGINAL REQUEST & CONTEXT:
{user}

ORIGINAL DRAFT:
=========================================
{draft_content}
=========================================

SENIOR BA REVIEWER FEEDBACK:
=========================================
{feedback}
=========================================

TASK: 
As the Final Editor, please provide the final, refined document. 
You MUST satisfy the original prompt and incorporate the REVIEWER FEEDBACK.
CRITICAL: Do not forget to output the required <json> structured data block at the end of your response, as instructed in your system prompt.
"""
        final_content = await self.llm.chat(system=system, user=editor_user_prompt, max_tokens=max_tokens)

        # Safety Fallback: if Editor output is weirdly short
        if not final_content or len(final_content) < len(draft_content) * 0.4:
            log.warning("doc_pipeline.refine_failed", reason="too short, using draft")
            return draft_content

        log.info("doc_pipeline.done")
        return final_content
