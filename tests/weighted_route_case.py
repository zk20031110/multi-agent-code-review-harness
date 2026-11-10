from __future__ import annotations

from textwrap import dedent
from typing import TypedDict


class BugCase(TypedDict):
    name: str
    task: str
    buggy_files: dict[str, str]
    fixed_files: dict[str, str]


def _file(content: str) -> str:
    """去除缩进，保持嵌入到评测数据中的源码可读。"""
    return dedent(content).lstrip()


TEST_ROUTER = _file(
    '''
    import pytest
    from router import shortest_path


    def test_shortest_cost_and_directed_edges():
        edges = [('s', 'a', 8), ('s', 'b', 2), ('b', 'a', 1), ('a', 't', 2)]
        assert shortest_path(['s', 'a', 'b', 't'], edges, 's', 't') == (
            ['s', 'b', 'a', 't'], 5
        )


    def test_equal_cost_prefers_fewer_edges_then_lexicographic_path():
        nodes = ['s', 'a', 'b', 't']
        direct_tie = [('s', 't', 2), ('s', 'a', 1), ('a', 't', 1)]
        assert shortest_path(nodes, direct_tie, 's', 't') == (['s', 't'], 2)

        # 两条路径成本和边数相同，但较早访问到的路径并非字典序最小路径。
        lexical_tie = [('s', 'b', 1), ('b', 't', 4), ('s', 'a', 5), ('a', 't', 0)]
        assert shortest_path(nodes, lexical_tie, 's', 't') == (['s', 'a', 't'], 5)


    def test_parallel_edges_keep_minimum_weight():
        edges = [('s', 'a', 9), ('s', 'a', 2), ('a', 't', 2), ('s', 't', 5)]
        assert shortest_path(['s', 'a', 't'], edges, 's', 't') == (
            ['s', 'a', 't'], 4
        )


    def test_zero_weight_cycle_does_not_repeat_nodes():
        edges = [('s', 'a', 0), ('a', 's', 0), ('a', 't', 1), ('s', 't', 1)]
        assert shortest_path(['s', 'a', 't'], edges, 's', 't') == (['s', 't'], 1)


    def test_start_equals_goal_and_unreachable():
        nodes = ['s', 't', 'x']
        assert shortest_path(nodes, [('s', 't', 1)], 's', 's') == (['s'], 0)
        assert shortest_path(nodes, [('s', 't', 1)], 't', 's') is None


    @pytest.mark.parametrize('weight', [-1, True, 1.5])
    def test_invalid_weight_is_rejected(weight):
        with pytest.raises(ValueError):
            shortest_path(['s', 't'], [('s', 't', weight)], 's', 't')


    def test_duplicate_nodes_and_unknown_edge_endpoint_are_rejected():
        with pytest.raises(ValueError):
            shortest_path(['s', 's', 't'], [], 's', 't')
        with pytest.raises(ValueError):
            shortest_path(['s', 't'], [('s', 'x', 1)], 's', 't')


    @pytest.mark.parametrize(('start', 'goal'), [('x', 't'), ('s', 'x')])
    def test_unknown_query_node_is_rejected(start, goal):
        with pytest.raises(ValueError):
            shortest_path(['s', 't'], [], start, goal)


    def test_inputs_are_not_mutated():
        nodes = ['s', 'a', 't']
        edges = [('s', 'a', 1), ('a', 't', 1)]
        original_nodes, original_edges = nodes.copy(), edges.copy()
        shortest_path(nodes, edges, 's', 't')
        assert nodes == original_nodes
        assert edges == original_edges
    '''
)


WEIGHTED_ROUTE_CASE: BugCase = {
    "name": "weighted_route_multifile",
    "task": (
        "修复多文件加权有向图路由模块。graph.py 的 build_adjacency(nodes, edges) "
        "负责校验输入并生成邻接表；router.py 的 shortest_path(nodes, edges, start, goal) "
        "依赖 graph.py 并使用 Dijkstra 返回 (path, cost) 或不可达时返回 None。"
        "节点必须是非空字符串且不能重复；边必须是 (source, destination, weight)，"
        "两端都必须存在于 nodes 中；weight 必须是非负整数，bool 和浮点数不合法。"
        "图为有向图；重复有向边保留最小权重；路径不得重复经过节点。"
        "先按总成本升序选择路径，成本相同则选边数更少的路径，再按完整节点序列的"
        "字典序选择；start == goal 返回 ([start], 0)，未知起点或终点抛 ValueError。"
        "不得修改传入的 nodes 或 edges。确保所有测试通过，并保留 graph.py 与 router.py 的模块边界。"
    ),
    "buggy_files": {
        "graph.py": _file(
            '''
            def build_adjacency(nodes, edges):
                adjacency = {node: {} for node in nodes}
                for source, destination, weight in edges:
                    adjacency.setdefault(source, {})[destination] = weight
                return adjacency
            '''
        ),
        "router.py": _file(
            '''
            import heapq
            from graph import build_adjacency


            def shortest_path(nodes, edges, start, goal):
                adjacency = build_adjacency(nodes, edges)
                queue = [(0, start)]
                distance = {start: 0}
                previous = {}
                while queue:
                    cost, node = heapq.heappop(queue)
                    if node == goal:
                        break
                    for neighbor, weight in adjacency.get(node, {}).items():
                        candidate = cost + weight
                        if candidate < distance.get(neighbor, float('inf')):
                            distance[neighbor] = candidate
                            previous[neighbor] = node
                            heapq.heappush(queue, (candidate, neighbor))
                if goal not in distance:
                    return None
                path = [goal]
                while path[-1] != start:
                    path.append(previous[path[-1]])
                return list(reversed(path)), distance[goal]
            '''
        ),
        "test_router.py": TEST_ROUTER,
    },
    "fixed_files": {
        "graph.py": _file(
            '''
            from collections.abc import Iterable, Sequence


            Edge = tuple[str, str, int]


            def build_adjacency(
                nodes: Sequence[str], edges: Iterable[Edge]
            ) -> dict[str, dict[str, int]]:
                node_list = list(nodes)
                if any(not isinstance(node, str) or not node.strip() for node in node_list):
                    raise ValueError('nodes must contain non-empty strings')
                if len(set(node_list)) != len(node_list):
                    raise ValueError('nodes must be unique')

                adjacency = {node: {} for node in node_list}
                for edge in edges:
                    try:
                        source, destination, weight = edge
                    except (TypeError, ValueError) as exc:
                        raise ValueError(
                            'each edge must contain source, destination, and weight'
                        ) from exc
                    if not isinstance(source, str) or not isinstance(destination, str):
                        raise ValueError('edge endpoints must be strings')
                    if source not in adjacency or destination not in adjacency:
                        raise ValueError('edge endpoint is not declared in nodes')
                    if isinstance(weight, bool) or not isinstance(weight, int) or weight < 0:
                        raise ValueError('weight must be a non-negative integer')

                    old_weight = adjacency[source].get(destination)
                    if old_weight is None or weight < old_weight:
                        adjacency[source][destination] = weight
                return adjacency
            '''
        ),
        "router.py": _file(
            '''
            from collections.abc import Iterable, Sequence
            from heapq import heappop, heappush
            from typing import TypeAlias

            from graph import Edge, build_adjacency


            Route: TypeAlias = tuple[list[str], int]


            def shortest_path(
                nodes: Sequence[str],
                edges: Iterable[Edge],
                start: str,
                goal: str,
            ) -> Route | None:
                adjacency = build_adjacency(nodes, edges)
                if start not in adjacency or goal not in adjacency:
                    raise ValueError('start and goal must be declared in nodes')

                initial_path = (start,)
                initial = (0, 0, initial_path)
                best: dict[str, tuple[int, int, tuple[str, ...]]] = {start: initial}
                queue: list[tuple[int, int, tuple[str, ...], str]] = [
                    (0, 0, initial_path, start)
                ]

                while queue:
                    cost, hops, path, node = heappop(queue)
                    current = (cost, hops, path)
                    if best.get(node) != current:
                        continue
                    if node == goal:
                        return list(path), cost

                    for neighbor, weight in adjacency[node].items():
                        if neighbor in path:
                            continue
                        candidate = (cost + weight, hops + 1, path + (neighbor,))
                        if neighbor not in best or candidate < best[neighbor]:
                            best[neighbor] = candidate
                            heappush(queue, (*candidate, neighbor))
                return None
            '''
        ),
        "test_router.py": TEST_ROUTER,
    },
}
