#!/usr/bin/env python

def test_api_help(client):
    response = client.get("/api/help")
    assert "/favicon.ico" in response
