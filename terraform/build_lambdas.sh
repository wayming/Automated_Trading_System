#!/bin/bash
mkdir -p build
for fn in handle_connect handle_disconnect handle_sendmessage post_connect_worker; do
  zip -j build/$fn.zip lambda/$fn/index.py
done
