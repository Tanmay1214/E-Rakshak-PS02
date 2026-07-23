"""E-RAKSHAK Part B: Application-Specific Acquisition Components.

Provides application-specific evidence acquisition and processing functionality
separate from the generic Part A acquisition pipeline.

Supported apps:
- WhatsApp: Key capture, decryption, database staging (existing).
- Telegram: Package detection, database group pulling, shared media inventory (Phase B.2.1).
- Signal: Package detection, database group pulling, shared media inventory, conservative parsing.
"""
from __future__ import annotations
