"""Orbit-camera script ownership and legacy D-pad movement migration.

Old SG3D projects commonly contain OnKeyHeld(arrow) -> MovePlayer(world XZ).
The built-in orbit controller cannot ALSO move that player: adding world and
camera-relative displacements makes navigation rotate incorrectly. We choose
script-owned input when a D-pad graph drives the orbit target and reinterpret
only its directional movement nodes in camera space. Original project JSON is
never modified, and non-orbit / unrelated movement semantics stay intact.
"""

DIRECTIONS = frozenset(('UP', 'DOWN', 'LEFT', 'RIGHT'))
MOTION = frozenset(('MovePlayer', 'MoveRelative', 'MoveObject'))


def orbit_script_controls(scene):
    """Return set of D-pad-driven movement node IDs for the orbit target.

    Also recognize explicit MoveRelative nodes as manually owned controls,
    even when custom nodes handle the input. Called by PC and GBA exporters.
    """
    orbit=((scene.get('camera') or {}).get('orbit') or {})
    if not orbit.get('enabled', False):
        return set()
    try:
        target=int(orbit.get('target',(scene.get('camera') or {}).get('follow',0)))
    except (ValueError, TypeError):
        return set()
    graph=scene.get('scripts') or {}
    nodes={str(n.get('id')):n for n in graph.get('nodes',[])}
    edges={}
    for link in graph.get('links',[]):
        edges.setdefault(str(link.get('from')),[]).append((str(link.get('port','next')),str(link.get('to'))))
    owned=set()
    def visits(node_id,directional,seen):
        if (node_id,directional) in seen:return
        seen.add((node_id,directional))
        node=nodes.get(node_id)
        if not node:return
        kind=node.get('type')
        p=node.get('params') or {}
        try:idx=int(p.get('object',-1))
        except (ValueError,TypeError):idx=-1
        if directional and kind in MOTION and idx==target:
            owned.add(node_id)
        for port,child in edges.get(node_id,[]):
            is_directional=directional
            if kind=='IfKeyHeld' and str(p.get('key','')).upper() in DIRECTIONS:
                is_directional = directional or port=='true'
            visits(child,is_directional,seen)
    for nid,node in nodes.items():
        p=node.get('params') or {}
        kind=node.get('type')
        if kind in ('OnKeyHeld','OnKeyPressed'):
            visits(nid,str(p.get('key','')).upper() in DIRECTIONS,set())
        elif kind=='OnUpdate':
            visits(nid,False,set())
        # A hand-authored MoveRelative node owns its own movement, whether
        # it comes from button events or an OnUpdate graph.
        if kind=='MoveRelative':
            try:
                if int(p.get('object',-1))==target:owned.add(nid)
            except (ValueError,TypeError):pass
    return owned
