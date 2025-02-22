import asyncio
import json
from http.client import HTTPException
from queue import Queue

from typing import List, Optional, Dict

import litellm

from fastapi import Header, HTTPException
from fastapi.responses import StreamingResponse

from core.logger import warn, info, error
from core.models import AssetsModels, ModelInfo, resolve_model_record
from core.repositories.stats_repository import UsageStatRecord
from core.routers.router_auth import AuthRouter
from core.routers.chat_models import ChatPost, ChatMessage


def increment_stats_record(rec: UsageStatRecord, model_record: ModelInfo, usage: Dict):
    try:
        rec.tokens_in += usage["prompt_tokens"]
        rec.tokens_out += usage["completion_tokens"]
        try:
            rec.dollars_in += round(usage["prompt_tokens"] / 1_000_000 * model_record.dollars_input, 5)
            rec.dollars_out += round(usage["completion_tokens"] / 1_000_000 * model_record.dollars_output, 5)
        except Exception:
            pass
    except Exception:
        pass


async def litellm_completion_stream(
        model_name: str,
        messages: List[ChatMessage],
        model_record: ModelInfo,
        post: ChatPost,
        stats_record: UsageStatRecord,
        stats_q: Queue,
):
    prefix, postfix = "data: ", "\n\n"
    finish_reason = None

    if 1:
        yield prefix + json.dumps(
            {"id": "chatcmpl-123", "object": "chat.completion.chunk", "created": 1694268190, "model": "",
             "system_fingerprint": "", "choices": [
                {"index": 0, "delta": {"role": "assistant", "content": "1"}, "logprobs": None,
                 "finish_reason": None}
            ]}) + postfix
        await asyncio.sleep(1)
        yield prefix + json.dumps(
            {"id": "chatcmpl-123", "object": "chat.completion.chunk", "created": 1694268190, "model": "",
             "system_fingerprint": "", "choices": [
                {"index": 0, "delta": {"role": "assistant", "content": "2"}, "logprobs": None,
                 "finish_reason": None}
            ]}) + postfix
        await asyncio.sleep(1)
        yield prefix + json.dumps(
            {"id": "chatcmpl-123", "object": "chat.completion.chunk", "created": 1694268190, "model": "",
             "system_fingerprint": "", "choices": [
                {"index": 0, "delta": {"role": "assistant", "content": "3"}, "logprobs": None,
                 "finish_reason": None}
            ]}) + postfix
        await asyncio.sleep(1)
        yield prefix + json.dumps(
            {"id": "chatcmpl-123", "object": "chat.completion.chunk", "created": 1694268190, "model": "",
             "system_fingerprint": "", "choices": [
                {"index": 0, "delta": {"role": "assistant", "content": "4"}, "logprobs": None,
                 "finish_reason": None}
            ]}) + postfix
        await asyncio.sleep(1)
        yield prefix + json.dumps(
            {"id": "chatcmpl-123", "object": "chat.completion.chunk", "created": 1694268190, "model": "",
             "system_fingerprint": "", "choices": [
                {"index": 0, "delta": {"role": "assistant", "content": "5"}, "logprobs": None,
                 "finish_reason": None}
            ]}) + postfix
        await asyncio.sleep(1)
        yield prefix + json.dumps(
            {"id": "chatcmpl-123", "object": "chat.completion.chunk", "created": 1694268190, "model": "",
             "system_fingerprint": "", "choices": [
                {"index": 0, "delta": {"role": "assistant", "content": "6"}, "logprobs": None,
                 "finish_reason": None}
            ]}) + postfix


    try:
        stream = await litellm.acompletion(
            model=model_name, messages=messages, stream=True,
            temperature=post.temperature, top_p=post.top_p,
            max_tokens=post.max_tokens,
            tools=post.tools,
            tool_choice=post.tool_choice,
            stop=post.stop if post.stop else None,
            n=post.n,
            stream_options={
                "include_usage": True,
            }
        )

        async for chunk in stream:
            try:
                data = chunk.model_dump()
                choice0 = data["choices"][0]
                finish_reason = choice0["finish_reason"]

                if usage := data.get("usage"):
                    increment_stats_record(stats_record, model_record, usage)
                if finish_reason:
                    stats_record.finish_reason = finish_reason

            except Exception as e:
                error(f"error in litellm_completion_stream: {e}")
                data = {"choices": [{"finish_reason": finish_reason}]}

            yield prefix + json.dumps(data) + postfix
    except Exception as e:
        err_msg = f"error in litellm_completion_stream: {e}"
        error(err_msg)
        yield prefix + json.dumps({"error": err_msg}) + postfix
    finally:
        stats_q.put(stats_record)


async def litellm_completion_not_stream(
        model_name: str,
        messages: List[ChatMessage],
        model_record: ModelInfo,
        post: ChatPost,
        stats_record: UsageStatRecord,
        stats_q: Queue,
):
    try:
        response = await litellm.acompletion(
            model=model_name, messages=messages, stream=False,
            temperature=post.temperature, top_p=post.top_p,
            max_tokens=post.max_tokens,
            tools=post.tools,
            tool_choice=post.tool_choice,
            stop=post.stop if post.stop else None,
            n=post.n,
        )
        response_dict = response.model_dump()

        if usage := response_dict.get("usage"):
            increment_stats_record(stats_record, model_record, usage)
        stats_q.put(stats_record)

        yield json.dumps(response_dict)

    except Exception as e:
        err_msg = f"error in litellm_completion_not_stream: {e}"
        error(err_msg)
        yield json.dumps({"error": err_msg})


class ChatCompletionsRouter(AuthRouter):
    def __init__(
            self,
            a_models: AssetsModels,
            stats_q: Queue,
            *args, **kwargs
    ):
        self._a_models = a_models
        self._stats_q = stats_q
        super().__init__(*args, **kwargs)

        self.add_api_route(f"/v1/chat/completions", self._chat_completions, methods=["POST"])

    async def _chat_completions(self, post: ChatPost, authorization: str = Header(None)):
        user = await self._check_auth(authorization)
        if not user:
            return self._auth_error_response()

        model_record: Optional[ModelInfo] = resolve_model_record(post.model, self._a_models)
        if not model_record:
            raise HTTPException(status_code=404, detail=f"Model {post.model} not found")

        if model_record.resolve_as not in litellm.model_list:
            warn(f"model {model_record.name} not in litellm.model_list")
        info(f"model resolve {post.model} -> {model_record.resolve_as}")

        stats_record = UsageStatRecord(
            user_id=user["user_id"],
            api_key=user["api_key"],
            model=model_record.resolve_as,
            tokens_in=0,
            tokens_out=0,
            dollars_in=0,
            dollars_out=0,
            messages_cnt=len(post.messages),
        )

        max_tokens = min(model_record.max_output_tokens, post.max_tokens) if post.max_tokens else post.max_tokens
        if post.max_tokens != max_tokens:
            info(f"model {model_record.name} max_tokens {post.max_tokens} -> {max_tokens}")
            post.max_tokens = max_tokens

        if model_record.backend == "litellm":
            response_streamer = litellm_completion_stream(
                model_record.resolve_as,
                post.messages,
                model_record,
                post,
                stats_record,
                self._stats_q,
            ) if post.stream else litellm_completion_not_stream(
                model_record.resolve_as,
                post.messages,
                model_record,
                post,
                stats_record,
                self._stats_q,
            )

        else:
            raise HTTPException(status_code=400, detail=f"Model {model_record.name}: Backend {model_record.backend} is not supported")

        async def custom_stream():
            async for chunk in response_streamer:
                info(f"chunk: {chunk}")
                yield chunk

        return StreamingResponse(custom_stream(), media_type="text/event-stream")
