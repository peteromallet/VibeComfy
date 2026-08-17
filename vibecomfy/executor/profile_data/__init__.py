"""Executor profile TOMLs shipped with VibeComfy.

These packaged TOMLs are the SOLE runtime authority for executor profile
specs: ``vibecomfy.executor.profiles`` loads from this package (or a test
override directory) and never consults an external Arnold package at
runtime, so VibeComfy works without an Arnold checkout.
"""
