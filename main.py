"""
柳州文旅智能体 - FastAPI 服务入口
- 认证: 注册 / 登录 / 登出 / 当前用户 (JWT 存 httpOnly Cookie)
- 对话: SSE 流式, 会话按登录用户隔离, 越权访问一律 404
- 静态: 构建后的 Vue 前端由本服务同源托管 (frontend/dist)

启动(开发): uvicorn main:app --host 0.0.0.0 --port 8000
启动(前端): cd frontend && npm run dev   # Vite 5173, /auth /chat /sessions 代理到 8000
"""
import json
import os
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Path as PathDep, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agent.multi_agent import MultiAgentService
from utils import auth
from utils.chat_history import (
    add_message,
    create_session,
    delete_session,
    get_messages,
    get_session,
    list_sessions,
)
from utils.file_reader import UPLOAD_ROOT, IMAGE_EXTS, is_allowed, read_file, save_uploaded_file
from utils.logger_handler import logger
from utils.path_tool import get_abs_path

app = FastAPI(title="柳州文旅智能体", description="景点咨询 / 美食推荐 / 行程规划 多智能体服务")

# 开发期允许 Vite 本地端口跨域携带 Cookie; 生产同源部署时该中间件不参与
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局唯一智能体实例: 模型与向量库只初始化一次, 所有请求复用
service = MultiAgentService()
# 滚动摘要缓存: 按会话ID隔离, 记录每个会话已生成的摘要与覆盖进度, 避免重复压缩
# (进程内缓存, 重启后自动重建, 不影响正确性——最多多做一次压缩)
summary_caches: dict[int, dict] = {}


class ChatRequest(BaseModel):
    query: str
    session_id: int | None = None
    # 用户上传并解析过的文件: [{name, content, file_type}]
    # 前端上传后把解析结果(文本)直接带过来, 后端不再重复解析
    uploaded_files: list[dict] | None = None


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=6, max_length=64)


class LoginRequest(BaseModel):
    username: str
    password: str


def _sse(event: str, data: dict) -> str:
    """按 SSE 规范格式化一帧事件"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _public_user(user: dict) -> dict:
    """只向前端暴露必要字段, 不返回密码哈希等敏感信息"""
    return {"id": user["id"], "username": user["username"]}


def _assert_owned_session(session_id: int, user: dict) -> dict:
    """
    校验会话归属: 不存在或不属于当前用户统一返回 404,
    避免通过状态码差异探测他人会话是否存在
    """
    session = get_session(session_id)
    if not session or session["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="会话不存在")
    return session


# ============ 认证接口 ============

@app.post("/auth/register")
def register(req: RegisterRequest, response: Response):
    """注册并直接登录, 下发 httpOnly Cookie"""
    try:
        user = auth.create_user(req.username, req.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    auth.set_auth_cookie(response, auth.issue_token(user))
    return {"user": _public_user(user)}


@app.post("/auth/login")
def login(req: LoginRequest, response: Response):
    user = auth.authenticate(req.username, req.password)
    if not user:
        # 不区分"用户不存在"与"密码错误", 防止账号枚举
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    auth.set_auth_cookie(response, auth.issue_token(user))
    return {"user": _public_user(user)}


@app.post("/auth/logout")
def logout(response: Response):
    auth.clear_auth_cookie(response)
    return {"ok": True}


@app.get("/auth/me")
def me(user: dict = Depends(auth.get_current_user)):
    return {"user": _public_user(user)}


# ============ 对话接口 ============

@app.get("/health")
def health():
    return {"status": "ok", "service": "柳州文旅智能体"}


# ============ 文件上传接口 ============

@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    user: dict = Depends(auth.get_current_user),
):
    """
    单文件上传 + 即时解析: 保存后用 file_reader 提取内容返回给前端,
    前端再把解析文本塞进 /chat 的 uploaded_files 字段
    """
    filename = file.filename or "unnamed"
    if not is_allowed(filename):
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {filename}")

    content = await file.read()
    if len(content) > 15 * 1024 * 1024:   # 15MB 上限
        raise HTTPException(status_code=400, detail="文件过大, 限制 15MB")

    abs_path, ext = save_uploaded_file(filename, content, user_id=user["id"])
    file_type, text = read_file(abs_path)

    # 计算相对路径: 前端用 /files/{relative_path} 就能访问 (同源托管)
    relative_path = os.path.relpath(abs_path, UPLOAD_ROOT).replace(os.sep, "/")

    # 截取过长内容 (传给前端的是预览, 完整内容在 /chat 里再用)
    preview = text[:2000] + ("\n...(内容过长, 仅显示前 2000 字)" if len(text) > 2000 else "")

    return {
        "name": filename,
        "file_type": file_type,
        "size": len(content),
        "preview": preview,
        "relative_path": relative_path,   # 持久化访问路径, 刷新后仍可用
        "is_image": ext in IMAGE_EXTS,
        # 完整内容也返回给前端, 发送消息时会一并带回来
        "full_content": text,
    }


# ============ 对话接口 ============

@app.post("/chat")
def chat(req: ChatRequest, user: dict = Depends(auth.get_current_user)):
    """
    SSE 流式对话接口(需登录):
    1. session_id 为空则新建会话, 否则先校验归属再加载历史
    2. 历史超阈值时先做滚动摘要压缩, 再交给多智能体流式执行
    3. 思考/工具/回答的每个片段以 chunk 事件推送, 最终回答以 end 事件推送并落库
    4. uploaded_files 里的文件解析文本会作为额外上下文拼进 user message
    """
    query = req.query.strip()
    if not query and not req.uploaded_files:
        raise HTTPException(status_code=400, detail="query 或上传文件不能为空")

    # 把上传文件解析的文本合并成一段上下文
    file_context = None
    if req.uploaded_files:
        parts = []
        for f in req.uploaded_files:
            name = f.get("name", "未命名文件")
            ftype = f.get("file_type", "")
            content = f.get("full_content") or f.get("content") or ""
            if content:
                parts.append(f"【{ftype}】{name}\n{content}")
        if parts:
            file_context = "\n\n---\n\n".join(parts)
            logger.info(f"[chat]合并 {len(req.uploaded_files)} 个上传文件, 共 {len(file_context)} 字")

    # 首条消息发送时才创建会话, 避免空会话
    if req.session_id is None:
        title = query.strip()[:20] or "新对话"
        session_id = create_session(user_id=user["id"], title=title)
        history: list[dict] = []
    else:
        _assert_owned_session(req.session_id, user)
        session_id = req.session_id
        history = get_messages(session_id)

    # 滚动摘要压缩: 超过阈值时把旧消息压成摘要(system消息), 缓存按会话隔离复用
    cache = summary_caches.setdefault(session_id, {"summary": None, "count": 0})
    try:
        history, cache = service.compress_history(history, cache)
    except Exception as e:
        # 压缩失败不阻断对话, 退回未压缩历史
        logger.error(f"[chat]历史压缩失败, 使用原始历史: {e}")
        history = get_messages(session_id) if req.session_id is not None else []
    summary_caches[session_id] = cache

    # 消息落库: query 可能为空(仅上传文件), 此时用默认文案
    display_query = query or "（仅查看上传的文件）"

    # 组装上传文件的持久化元信息 (用于刷新后恢复图片预览)
    files_json = None
    if req.uploaded_files:
        meta_list = []
        for f in req.uploaded_files:
            item = {
                "name": f.get("name", ""),
                "file_type": f.get("file_type", ""),
                "relative_path": f.get("relative_path"),  # 可持久化访问路径
            }
            # 只有后端 upload 接口返回的文件才可能有 is_image 标识
            name_lower = item["name"].lower()
            item["is_image"] = item.get("is_image") or any(
                name_lower.endswith(ext) for ext in IMAGE_EXTS
            )
            if item["relative_path"]:   # 有可访问路径才存 (确保刷新后能恢复)
                meta_list.append(item)
        if meta_list:
            files_json = json.dumps(meta_list, ensure_ascii=False)

    add_message(session_id, "user", display_query, files_json=files_json)

    def event_stream():
        # 首帧先告知会话ID, 前端保存后后续请求携带以维持上下文
        first_frame = {"session_id": session_id}
        if req.uploaded_files:
            first_frame["uploaded_names"] = [f.get("name") for f in req.uploaded_files]
        yield _sse("session", first_frame)

        parts: list[str] = []
        try:
            for chunk in service.execute_stream(query, history, file_context=file_context):
                parts.append(chunk)
                yield _sse("chunk", {"text": chunk})
        except Exception as e:
            # 网络瞬断/模型超时等: 已有片段仍落库 + 正常发 end, 前端至少能看到已生成的内容
            logger.error(f"[chat]对话执行中断: {e}", exc_info=True)
            partial = "".join(parts).strip()
            if partial:
                add_message(session_id, "assistant", partial)
                yield _sse("end", {"answer": partial})
            else:
                yield _sse("end", {"answer": ""})
            yield _sse("error", {"message": "回答尚未完成，请稍后再问一次"})
            return

        # 逐token流式下回答由所有片段拼接而成, 落库供下轮作为历史
        answer = "".join(parts).strip()
        if answer:
            add_message(session_id, "assistant", answer)
        yield _sse("end", {"answer": answer})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/sessions")
def get_session_list(user: dict = Depends(auth.get_current_user)):
    """当前用户的会话列表, 按最近更新倒序; 他人的会话永远不会出现在结果中"""
    return list_sessions(user["id"])


@app.get("/sessions/{session_id}/messages")
def get_session_messages(session_id: int, user: dict = Depends(auth.get_current_user)):
    """指定会话的全部历史消息(仅限本人)"""
    _assert_owned_session(session_id, user)
    return get_messages(session_id)


@app.delete("/sessions/{session_id}")
def remove_session(session_id: int, user: dict = Depends(auth.get_current_user)):
    """删除会话及其全部消息(仅限本人), 同步清理摘要缓存"""
    _assert_owned_session(session_id, user)
    delete_session(session_id)
    summary_caches.pop(session_id, None)
    return {"deleted": session_id}


# ============ 上传文件访问接口 (同源托管) ============

@app.get("/files/{file_path:path}")
def serve_uploaded_file(file_path: str, user: dict = Depends(auth.get_current_user)):
    """
    访问用户上传的文件(图片/文档等), 同源托管;
    仅允许访问 data/uploads/ 下的文件, 防止路径穿越
    """
    upload_root = os.path.normpath(UPLOAD_ROOT)
    target = os.path.normpath(os.path.join(upload_root, file_path))

    # 路径穿越检查
    if not target.startswith(upload_root + os.sep) and target != upload_root:
        raise HTTPException(status_code=400, detail="路径非法")
    if not os.path.isfile(target):
        raise HTTPException(status_code=404, detail="文件不存在")

    # 额外安全: 如果路径形如 "<user_id>/filename", 确认 user_id 匹配
    # 让用户只能访问自己上传的文件
    rel = os.path.relpath(target, upload_root).replace(os.sep, "/")
    parts = rel.split("/")
    if parts and parts[0].isdigit() and int(parts[0]) != user["id"]:
        raise HTTPException(status_code=403, detail="无权访问此文件")

    return FileResponse(target)


# ============ 前端静态资源(构建产物存在时同源托管) ============
DIST_DIR = get_abs_path("frontend/dist")

if os.path.isdir(DIST_DIR):
    assets_dir = os.path.join(DIST_DIR, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        """SPA 路由回退: 静态文件存在则返回文件, 否则交给前端路由处理"""
        candidate = os.path.join(DIST_DIR, full_path)
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(DIST_DIR, "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
