"""HTTP client that adapts a unified TestCase to JSON+dataurl or multipart contracts."""
import base64
import mimetypes
from pathlib import Path

import requests


class TargetError(Exception):
    pass


def _data_url(path: Path):
    mime, _ = mimetypes.guess_type(str(path))
    if mime is None:
        # fallback by suffix for the common multimodal types
        suf = Path(path).suffix.lower()
        mime = {
            ".mp3": "audio/mpeg",
            ".wav": "audio/wav",
            ".m4a": "audio/mp4",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".pdf": "application/pdf",
            ".mp4": "video/mp4",
            ".webm": "video/webm",
            ".mov": "video/quicktime",
        }.get(suf, "application/octet-stream")
    b64 = base64.b64encode(Path(path).read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}", mime


class TargetClient:
    def __init__(self, url: str, contract: str = "json_dataurl",
                 timeout: int = 30, retries: int = 1):
        self.url = url
        self.contract = contract
        self.timeout = timeout
        self.retries = max(0, int(retries))

    def send(self, message: str, attachment_path: Path = None, history=None):
        last_exc = None
        for _ in range(self.retries + 1):
            try:
                if self.contract == "json_dataurl":
                    return self._send_json(message, attachment_path, history)
                if self.contract == "multipart":
                    return self._send_multipart(message, attachment_path)
                raise TargetError(f"Unknown contract: {self.contract}")
            except requests.RequestException as e:
                last_exc = e
        raise TargetError(f"Request failed: {last_exc}")

    def _send_json(self, message, attachment_path, history):
        body = {"message": message, "history": history or []}
        if attachment_path:
            data_url, mime = _data_url(attachment_path)
            body["attachment"] = {
                "data": data_url,
                "mime": mime,
                "name": Path(attachment_path).name,
            }
        resp = requests.post(self.url, json=body, timeout=self.timeout)
        return self._extract(resp)

    def _send_multipart(self, message, attachment_path):
        data = {"message": message}
        files = {}
        if attachment_path:
            files["files"] = (Path(attachment_path).name, open(attachment_path, "rb"))
        try:
            resp = requests.post(self.url, data=data, files=files or None,
                                 timeout=self.timeout)
        finally:
            for f in files.values():
                try:
                    f[1].close()
                except Exception:
                    pass
        return self._extract(resp)

    def _extract(self, resp):
        try:
            payload = resp.json()
        except ValueError:
            return {"reply": resp.text, "status": resp.status_code, "raw": resp.text}
        reply = (payload.get("reply") or payload.get("answer")
                 or payload.get("response") or payload.get("error") or "")
        return {"reply": reply, "status": resp.status_code, "raw": payload}
