#!/usr/bin/env python3
"""Interactive CLI script for first-time authentication of the Telethon user account."""

import asyncio
import getpass
import sys
from pathlib import Path

from telethon import TelegramClient
from telethon.errors import (
    PasswordHashInvalidError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    PhoneNumberInvalidError,
    SessionPasswordNeededError,
)

from app.core.config import get_settings


async def main() -> None:
    settings = get_settings()

    print("=" * 60)
    print("🔐 Telethon First-Time Authentication Setup")
    print("=" * 60)
    print(f"API ID:       {settings.API_ID}")
    print(f"Session Path: {settings.TELEGRAM_SESSION}")
    print("=" * 60)

    # Ensure target session directory exists
    session_file = Path(settings.TELEGRAM_SESSION).resolve()
    session_file.parent.mkdir(parents=True, exist_ok=True)

    client = TelegramClient(
        session=str(session_file),
        api_id=settings.API_ID,
        api_hash=settings.API_HASH,
    )

    await client.connect()

    if await client.is_user_authorized():
        me = await client.get_me()
        print("\n✅ Session is ALREADY authenticated!")
        print(f"• Name:     {getattr(me, 'first_name', '')} {getattr(me, 'last_name', '') or ''}")
        print(f"• Username: @{getattr(me, 'username', 'None')}")
        print(f"• User ID:  {getattr(me, 'id', '')}")
        print(f"• Saved at: {session_file}")
        await client.disconnect()
        return

    phone = input("\nEnter your phone number with country code (e.g. +1234567890): ").strip()
    if not phone:
        print("❌ Phone number cannot be empty.")
        await client.disconnect()
        sys.exit(1)

    try:
        sent = await client.send_code_request(phone)
        phone_code_hash = sent.phone_code_hash
    except PhoneNumberInvalidError:
        print("❌ The phone number entered is invalid.")
        await client.disconnect()
        sys.exit(1)
    except Exception as exc:
        print(f"❌ Failed to request verification code: {exc}")
        await client.disconnect()
        sys.exit(1)

    code = input("Enter the login code you received in Telegram: ").strip()

    try:
        await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
    except SessionPasswordNeededError:
        # Two-step verification (2FA) is enabled
        password = getpass.getpass("Two-step verification enabled. Enter your 2FA password: ")
        try:
            await client.sign_in(password=password)
        except PasswordHashInvalidError:
            print("❌ Invalid 2FA password.")
            await client.disconnect()
            sys.exit(1)
    except (PhoneCodeInvalidError, PhoneCodeExpiredError):
        print("❌ The verification code entered is invalid or expired.")
        await client.disconnect()
        sys.exit(1)
    except Exception as exc:
        print(f"❌ Login error: {exc}")
        await client.disconnect()
        sys.exit(1)

    me = await client.get_me()
    print("\n🎉 Authentication SUCCESSFUL!")
    print(f"• Name:     {getattr(me, 'first_name', '')} {getattr(me, 'last_name', '') or ''}")
    print(f"• Username: @{getattr(me, 'username', 'None')}")
    print(f"• User ID:  {getattr(me, 'id', '')}")
    print(f"• Session:  {session_file}")
    print("\nYou can now launch the application using: python -m app.main")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
