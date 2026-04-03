from fastapi import Depends, HTTPException, status
from apps.api.auth.dependencies import CurrentUser, get_current_user

async def validate_project_access(project_key: str, user: CurrentUser = Depends(get_current_user)):
    """
    Dependency dùng để kiểm tra quyền truy cập vào một dự án cụ thể.
    Quy ước: Project 'ABC' sẽ tương ứng với group 'group_jira_project_abc'.
    """
    if not project_key:
        return True # Phụ thuộc vào endpoint cho phép empty hay không
        
    if user.is_admin:
        return True
        
    pk_lower = str(project_key).lower().strip()
    # Danh sách các group tiềm năng ánh xạ tới project này
    required_groups = {
        f"group_jira_project_{pk_lower}",
        f"group_confluence_space_{pk_lower}",
        f"group_project_{pk_lower}",
        f"group_{pk_lower}"
    }
    
    user_groups = set(user.groups or [])
    if not (required_groups & user_groups):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail=f"Bạn không có quyền truy cập dự án '{project_key}'. Vui lòng liên hệ Admin để được cấp quyền vào nhóm tương ứng."
        )
    return True

def get_accessible_projects(user: CurrentUser) -> list[str]:
    """Trả về danh sách Project Keys mà user có quyền truy cập dựa trên Groups."""
    if user.is_admin:
        return [] # Admin có quyền xem tất cả, xử lý ở SQL bằng cách skip filter
        
    projects = []
    for g in (user.groups or []):
        if g.startswith("group_jira_project_"):
            projects.append(g.replace("group_jira_project_", "").upper())
        elif g.startswith("group_project_"):
            projects.append(g.replace("group_project_", "").upper())
            
    return sorted(list(set(projects)))
