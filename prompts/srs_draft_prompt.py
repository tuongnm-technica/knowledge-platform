def build_srs_system_prompt(*args, **kwargs) -> str:
    """
    Xây dựng system prompt cho việc tạo tài liệu SRS (Software Requirements Specification).
    """
    return (
        "You are an expert technical writer and Business Analyst. "
        "Your task is to generate a highly professional and structured Software Requirements Specification (SRS) "
        "document based on the provided context."
    )

def build_srs_user_prompt(*args, **kwargs) -> str:
    """
    Xây dựng user prompt cho việc tạo tài liệu SRS.
    """
    context = kwargs.get("context", "")
    goal = kwargs.get("goal", "")
    title = kwargs.get("title", "Untitled Document")
    
    return f"Generate a document draft with the title: '{title}'.\n\nGoal:\n{goal}\n\nContext Information:\n{context}\n\nPlease output in Markdown format."