from connectors.confluence.confluence_client import ConfluenceClient


class ConfluencePermissions:
    def __init__(self, client: ConfluenceClient):
        self._client = client

    def get_permitted_groups(self, page_id: str, space_key: str) -> list[str]:
        restrictions = self._client.get_page_restrictions(page_id)
        groups = [f"confluence_space_{space_key}"]

        for restriction in restrictions:
            subject = restriction.get("subject", {})
            if subject.get("type") == "group":
                group_name = subject.get("identifier", "")
                if group_name:
                    groups.append(f"confluence_group_{group_name}")

        return list(set(groups))