"""Fixed graph/DFS architecture. Only the supplied LLM order is learned guidance."""
from disassembly_hybrid.graph import ConditionalBlockingGraph,canonical_candidates,physical_state_key,action_key

class DFS:
    def __init__(self):
        self.graph=ConditionalBlockingGraph();self.stack=[];self.nodes={};self.exhausted=set()
        self.order=[];self.failures_since_rank=0;self.epoch=0
    def frame(self,sim,api):
        key=physical_state_key(sim.export_state())
        if self.stack and self.stack[-1]['key']==key:return self.stack[-1]
        node=self.nodes.get(key)
        if node is None:
            node=dict(key=key,handle=api.checkpoint(),attempted=set(),children={})
            self.nodes[key]=node
        self.stack.append(node);self.epoch+=1
        return node
    def candidates(self,sim,api):
        f=self.frame(sim,api)
        rows=self.graph.filter(f['key'],canonical_candidates(api.snapshot()))
        return [r for r in rows if action_key(r) not in f['attempted'] and f['children'].get(action_key(r)) not in self.exhausted]
    def context(self,sim,api):
        f=self.frame(sim,api)
        return dict(candidate_actions=self.candidates(sim,api),directed_graph=self.graph.describe(f['key']),
                    dfs_depth=len(self.stack)-1,visited_nodes=len(self.nodes),exhausted_nodes=len(self.exhausted))
    def set_order(self,proposed,candidates):
        allowed={action_key(a):a for a in candidates};seen=set();ordered=[]
        for a in proposed:
            if not isinstance(a,dict) or set(a)!={'part_id','direction'}:continue
            key=action_key(a)
            if key in allowed and key not in seen:ordered.append(dict(a));seen.add(key)
        self.order=ordered+[dict(a) for a in candidates if action_key(a) not in seen]
        self.failures_since_rank=0
    def step(self,sim,api):
        f=self.frame(sim,api);candidates=self.candidates(sim,api)
        if not candidates:
            self.exhausted.add(f['key']);self.stack.pop()
            if not self.stack:return 'exhausted'
            api.restore(self.stack[-1]['handle']);self.epoch+=1
            return 'restored'
        ranks={action_key(a):i for i,a in enumerate(self.order)}
        action=min(candidates,key=lambda a:ranks.get(action_key(a),len(ranks)))
        pair=action_key(action);f['attempted'].add(pair)
        result=api.remove(action['part_id'],action['direction']);self.graph.add(f['key'],result)
        if result['valid']:
            f['children'][pair]=physical_state_key(sim.export_state())
            if not sim.success:self.frame(sim,api)
            return 'descended'
        self.failures_since_rank+=1
        return 'rejected'
