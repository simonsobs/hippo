"""Collection permission commands, exercised without a live server."""

import json
from collections import Counter

import httpx
import pytest
from rich.console import Console
from typer.testing import CliRunner

from hippoclient import cli, collections

ROOT, CHILD, SIBLING, GRANDCHILD = [f"{i:024x}" for i in range(1, 5)]
PRODUCT, SHARED_PRODUCT, NESTED_PRODUCT = [f"{i:024x}" for i in range(5, 8)]
OLD_PRODUCT = f"{8:024x}"
ACTIONS = ["add-reader", "remove-reader", "add-writer", "remove-writer"]


def collection_summary(id):
    return {
        "id": id,
        "name": id,
        "description": "",
        "owner": "owner",
        "readers": ["team"],
        "writers": ["team"],
    }


def collection_response(id, children=(), products=()):
    return {
        **collection_summary(id),
        "child_collections": [collection_summary(child) for child in children],
        "products": [
            {
                "id": product,
                "name": product,
                "description": "",
                "owner": "owner",
                "version": "1.0.0",
                "uploaded": "2026-01-01T00:00:00Z",
                "metadata": None,
            }
            for product in products
        ],
    }


def product_tree(id):
    metadata = {
        **collection_response(ROOT, products=[id])["products"][0],
        "current": True,
        "updated": "2026-01-01T00:00:00Z",
        "sources": {},
        "replaces": None,
        "child_of": [],
        "parent_of": [],
        "collections": [],
    }
    return {
        "current_present": True,
        "current": "1.0.0",
        "requested": "1.0.0",
        "versions": {"1.0.0": metadata},
    }


@pytest.fixture
def permission_server():
    # Shared descendants and a cycle must not lead to repeated updates.
    graph = {
        ROOT: collection_response(ROOT, [CHILD, SIBLING], [PRODUCT]),
        CHILD: collection_response(CHILD, [GRANDCHILD], [SHARED_PRODUCT]),
        SIBLING: collection_response(SIBLING, [GRANDCHILD], [SHARED_PRODUCT]),
        GRANDCHILD: collection_response(GRANDCHILD, [ROOT], [NESTED_PRODUCT]),
    }
    requests = []
    failures = {}
    trees = {id: product_tree(id) for id in (PRODUCT, SHARED_PRODUCT, NESTED_PRODUCT)}

    def handle(request):
        requests.append(request)
        path = request.url.path
        if (request.method, path) in failures:
            return httpx.Response(failures[request.method, path])
        if request.method == "GET":
            if path.startswith("/product/"):
                return httpx.Response(200, json=trees[path.split("/")[2]])
            return httpx.Response(200, json=graph[path.rsplit("/", 1)[-1]])
        assert request.method == "POST"
        if path.startswith("/product/"):
            return httpx.Response(200, json={"id": path.split("/")[2]})
        return httpx.Response(200, json=path.rsplit("/", 1)[-1])

    with httpx.Client(
        base_url="https://hippo.test", transport=httpx.MockTransport(handle)
    ) as client:
        yield client, requests, failures, graph, trees


@pytest.mark.parametrize("command", ACTIONS)
@pytest.mark.parametrize("recursive", [False, True])
def test_collection_permission_command(
    command, recursive, permission_server, monkeypatch
):
    client, requests, _, _, _ = permission_server
    monkeypatch.setattr(cli, "CLIENT", client, raising=False)
    monkeypatch.setattr(cli, "CONSOLE", Console(quiet=True), raising=False)
    args = ["collection", command, ROOT, "team"]
    if recursive:
        args.append("--recursive")

    result = CliRunner().invoke(cli.APP, args)

    assert result.exit_code == 0, result.output
    updates = [request for request in requests if request.method == "POST"]
    collection_ids = [ROOT, CHILD, SIBLING, GRANDCHILD] if recursive else [ROOT]
    product_ids = [PRODUCT, SHARED_PRODUCT, NESTED_PRODUCT] if recursive else []
    expected_paths = [f"/relationships/collection/{id}" for id in collection_ids]
    expected_paths += [f"/product/{id}/update" for id in product_ids]
    assert Counter(request.url.path for request in updates) == Counter(expected_paths)
    action = command.replace("-", "_") + "s"
    for request in updates:
        expected = {action: ["team"]}
        if request.url.path.startswith("/product/"):
            expected["level"] = None
        assert json.loads(request.content) == expected

    reads = [request for request in requests if request.method == "GET"]
    expected_reads = [
        f"/relationships/collection/{id}" for id in collection_ids if recursive
    ]
    expected_reads += [f"/product/{id}/tree" for id in product_ids]
    assert Counter(request.url.path for request in reads) == Counter(expected_reads)
    if recursive:
        # All discovery must finish before removing any access.
        assert all(request.method == "GET" for request in requests[: len(reads)])


@pytest.mark.parametrize("command", ACTIONS)
def test_recursive_permission_returns_root_id(command, permission_server):
    client, _, _, _, _ = permission_server
    update = getattr(collections, command.replace("-", "_"))
    assert update(client, ROOT, "team", recursive=True) == ROOT


def test_recursive_discovery_failure_does_not_change_permissions(permission_server):
    client, requests, failures, _, _ = permission_server
    failures["GET", f"/relationships/collection/{CHILD}"] = 403

    with pytest.raises(httpx.HTTPStatusError):
        collections.remove_reader(client, ROOT, "team", recursive=True)

    assert all(request.method == "GET" for request in requests)


def test_recursive_product_failure_stops_updates(permission_server):
    client, requests, failures, _, _ = permission_server
    failures["POST", f"/product/{PRODUCT}/update"] = 403

    with pytest.raises(httpx.HTTPStatusError):
        collections.add_writer(client, ROOT, "team", recursive=True)

    updates = [request for request in requests if request.method == "POST"]
    assert len(updates) == 1
    assert updates[0].url.path == f"/product/{PRODUCT}/update"


@pytest.mark.parametrize("command", ACTIONS)
def test_recursive_permissions_resolve_and_deduplicate_versions(
    command, permission_server
):
    client, requests, _, graph, trees = permission_server
    graph[ROOT] = collection_response(ROOT, products=[OLD_PRODUCT, PRODUCT])
    trees[OLD_PRODUCT] = product_tree(PRODUCT)
    trees[OLD_PRODUCT]["requested"] = "0.9.0"
    trees[OLD_PRODUCT]["versions"]["0.9.0"] = {
        **trees[OLD_PRODUCT]["versions"]["1.0.0"],
        "id": OLD_PRODUCT,
        "version": "0.9.0",
        "current": False,
    }
    trees[OLD_PRODUCT]["versions"]["1.0.0"]["replaces"] = "0.9.0"

    update = getattr(collections, command.replace("-", "_"))
    assert update(client, ROOT, "team", recursive=True) == ROOT

    assert [request.url.path for request in requests if request.method == "POST"] == [
        f"/product/{PRODUCT}/update",
        f"/relationships/collection/{ROOT}",
    ]


def test_recursive_resolution_failure_does_not_change_permissions(permission_server):
    client, requests, failures, _, _ = permission_server
    failures["GET", f"/product/{SHARED_PRODUCT}/tree"] = 500

    with pytest.raises(httpx.HTTPStatusError):
        collections.remove_reader(client, ROOT, "team", recursive=True)

    assert all(request.method == "GET" for request in requests)
