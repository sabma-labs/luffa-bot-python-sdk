from __future__ import annotations
import argparse
import asyncio
import os
from .client import AsyncLuffaClient
from .models import GroupMessagePayload, SimpleButton

async def _echo_handler(msg, env, client: AsyncLuffaClient):
    if env.type == 0:
        await client.send_to_user(env.uid, f"Echo: {msg.text}")
    else:
        await client.send_to_group(env.uid, f"Echo: {msg.text}", message_type=1)

async def main_async():
    parser = argparse.ArgumentParser("luffa-bot", description="Run or send via Luffa bot.")
    sub = parser.add_subparsers(dest="cmd")

    p_run = sub.add_parser("run", help="Run echo bot")
    p_run.add_argument("--secret", help="Robot secret key")
    p_run.add_argument("--interval", type=float, default=1.0)
    p_run.add_argument("--concurrency", type=int, default=1)

    p_dm = sub.add_parser("send", help="Send DM to user")
    p_dm.add_argument("--secret")
    p_dm.add_argument("--uid", required=True)
    p_dm.add_argument("--text", required=True)

    p_grp = sub.add_parser("send-group", help="Send to group")
    p_grp.add_argument("--secret")
    p_grp.add_argument("--uid", required=True)
    p_grp.add_argument("--text", required=True)
    p_grp.add_argument("--with-buttons", action="store_true")

    args = parser.parse_args()
    secret = args.secret or os.getenv("LUFFA_ROBOT_SECRET")
    if not secret:
        raise SystemExit("Please set --secret or LUFFA_ROBOT_SECRET")

    from .polling import run as run_loop

    if args.cmd == "run":
        client = AsyncLuffaClient(secret)
        await run_loop(client, handler=_echo_handler, interval=args.interval, concurrency=args.concurrency)

    elif args.cmd == "send":
        client = AsyncLuffaClient(secret)
        await client.send_to_user(args.uid, args.text)
        print("Sent.")

    elif args.cmd == "send-group":
        client = AsyncLuffaClient(secret)
        if args.with_buttons:
            payload = GroupMessagePayload(
                text=args.text,
                button=[SimpleButton(name="OK", selector="ok", isHidden=0)],
                # dismissType optional
            )
            await client.send_to_group(args.uid, payload, message_type=2)
        else:
            await client.send_to_group(args.uid, args.text, message_type=1)
        print("Sent.")
    else:
        parser.print_help()

def main():
    asyncio.run(main_async())
