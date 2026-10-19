"""Trusted geometry checks and MuJoCo gravity/friction stability evaluation.

Extraction is sampled, kinematic path validation. Only the residual assembly
is integrated dynamically. This is deliberately NOT a force-driven extraction
or a robot/grasp simulation. All physical settings live in the case JSON.
"""
from pathlib import Path
import copy
import json
import math
import time
from xml.sax.saxutils import escape
import mujoco
import numpy as np
from scipy.spatial.transform import Rotation

DIRECTIONS = {'+x': [1,0,0], '-x': [-1,0,0], '+y': [0,1,0],
              '-y': [0,-1,0], '+z': [0,0,1], '-z': [0,0,-1]}
DEFAULT_PHYSICS = {
    'gravity': [0,0,-9.81], 'friction': 0.5, 'timestep': 0.002,
    'settle_seconds': 1.5, 'path_step_m': 0.001,
    'penetration_tolerance_m': 0.0002,
    'resting_contact_slack_m': 0.00002,
    'stable_translation_m': 0.005, 'stable_rotation_deg': 5.0,
    'stable_final_speed_m_s': 0.02, 'stable_penetration_m': 0.001, 'density_kg_m3': 1000.0,
    'solver_iterations': 100, 'contact_solref': [0.01,1.0],
}

def numbers(v): return ' '.join('%.12g' % float(x) for x in v)

def rotation_matrix(wxyz):
    return Rotation.from_quat([*wxyz[1:],wxyz[0]]).as_matrix()

def angle_degrees(a,b):
    dot = abs(float(np.dot(np.asarray(a),np.asarray(b))))
    return float(math.degrees(2*math.acos(min(1.,max(0.,dot)))))

class DisassemblySim:
    def __init__(self, case_path, max_checks=24, capture=False, state=None):
        self.case_path = Path(case_path).resolve()
        self.case = json.loads(self.case_path.read_text())
        self.parts = {p['id']:p for p in self.case['parts']}
        if len(self.parts) != len(self.case['parts']) or self.case.get('target_id') not in self.parts:
            raise ValueError('Case needs unique part IDs and an existing target')
        if self.parts[self.case['target_id']].get('fixed', False):
            raise ValueError('Target cannot be the fixed fixture')
        self.physics = {**DEFAULT_PHYSICS, **self.case.get('physics',{})}
        self.max_checks = max_checks
        self.capture = capture
        self.checks = 0
        self.trace = []
        self.actions = []
        self.frames = []
        self.events = []
        self.clock = 0.0
        self.remaining = list(self.parts)
        self.poses = {p['id']: {'position':p['position'],
                              'quaternion':p.get('quaternion',[1,0,0,0]),
                              'velocity':[0.]*6} for p in self.case['parts']}
        if self.case.get('initial_poses'):
            self.poses = copy.deepcopy(self.case['initial_poses'])
        if state is not None:
            self.restore_state(state)
        self._record_frame('초기 조립 상태')

    @property
    def success(self): return self.case['target_id'] not in self.remaining

    @property
    def target_removed(self): return self.success

    def export_state(self):
        return copy.deepcopy({'remaining':self.remaining,'poses':self.poses,
                              'checks':self.checks,'trace':self.trace,'actions':self.actions})

    def restore_state(self,state):
        self.remaining = list(state['remaining'])
        self.poses = copy.deepcopy(state['poses'])
        self.checks = int(state.get('checks',0))
        self.trace = copy.deepcopy(state.get('trace',[]))
        self.actions = copy.deepcopy(state.get('actions',[]))
        if not set(self.remaining).issubset(self.parts):
            raise ValueError('Unknown part in restored state')

    def _path(self, relative):
        return (self.case_path.parent / relative).resolve()

    def bounds(self,pid,poses=None):
        pose=(poses or self.poses)[pid]
        a,b=np.asarray(self.parts[pid]['local_bounds'])
        corners=np.array([[x,y,z] for x in [a[0],b[0]] for y in [a[1],b[1]] for z in [a[2],b[2]]])
        world=corners@rotation_matrix(pose['quaternion']).T+np.asarray(pose['position'])
        return np.stack([world.min(axis=0),world.max(axis=0)])

    def snapshot(self):
        return {'case_id':self.case['id'],'target_id':self.case['target_id'],
                'remaining_parts':[{'id':pid,'bounds':self.bounds(pid).round(6).tolist(),
                                    'center':self.poses[pid]['position'],
                                    'mass':self.parts[pid]['mass_kg'],
                                    'fixed':self.parts[pid].get('fixed',False),
                                    'allowed_directions':self.parts[pid].get('allowed_directions',list(DIRECTIONS))}
                                   for pid in self.remaining],
                'remaining_checks':max(0,self.max_checks-self.checks),
                'physics':self.physics,
                'scope':'Sampled straight extraction, then gravity/friction residual stability. No robot or force-driven extraction.'}

    observe=snapshot

    def _build(self, remaining=None, poses=None, gravity=None, friction=None):
        remaining=self.remaining if remaining is None else list(remaining)
        poses=self.poses if poses is None else poses
        cfg=self.physics
        mu=cfg['friction'] if friction is None else friction
        friction_values=mu if isinstance(mu,(list,tuple)) else [mu,0.005,0.0001]
        assets=[]; bodies=[]; body_names={}; geom_part={}
        for index,pid in enumerate(remaining):
            p=self.parts[pid];pose=poses[pid];name='p%d'%index;body_names[pid]=name
            visual='visual_%d'%index
            assets.append(f'<mesh name="{visual}" file="{escape(str(self._path(p["visual_mesh"])))}"/>')
            body=[f'<body name="{name}" pos="{numbers(pose["position"])}" quat="{numbers(pose["quaternion"])}">']
            if not p.get('fixed',False): body.append(f'<freejoint name="j_{name}"/>')
            inertia=p.get('inertia_diagonal')
            if inertia is None:
                dims=np.diff(np.asarray(p['local_bounds']),axis=0)[0]
                inertia=(p['mass_kg']/12*np.array([dims[1]**2+dims[2]**2,dims[0]**2+dims[2]**2,dims[0]**2+dims[1]**2])).tolist()
            body.append(f'<inertial pos="0 0 0" mass="{p["mass_kg"]}" diaginertia="{numbers(inertia)}"/>')
            color=p.get('color',[.3,.6,.7,1])
            if len(color)==3: color=[*color,1]
            body.append(f'<geom name="v_{name}" type="mesh" mesh="{visual}" contype="0" conaffinity="0" mass="0" group="2" rgba="{numbers(color)}"/>')
            for j,hull in enumerate(p['collision_meshes']):
                hn=f'c_{index}_{j}'
                assets.append(f'<mesh name="{hn}" file="{escape(str(self._path(hull)))}"/>')
                body.append(f'<geom name="{hn}" type="mesh" mesh="{hn}" mass="0" group="3" rgba="0.9 0.2 0.2 0"/>')
                geom_part[hn]=pid
            body.append('</body>');bodies.append(''.join(body))
        g=cfg['gravity'] if gravity is None else gravity
        xml=f'''<mujoco model="CAD_disassembly">
          <compiler angle="radian" autolimits="true"/>
          <option timestep="{cfg['timestep']}" gravity="{numbers(g)}" integrator="implicitfast"
           iterations="{cfg['solver_iterations']}" cone="elliptic"><flag multiccd="disable"/></option>
          <default><geom condim="3" friction="{numbers(friction_values)}" solref="{numbers(cfg['contact_solref'])}"/></default>
          <visual><global offwidth="1200" offheight="900"/></visual>
          <asset>{''.join(assets)}</asset><worldbody>
          <light pos="0 -1 2"/><geom name="floor" type="plane" size="1 1 .02" rgba="0.82 0.85 0.88 1"/>
          {''.join(bodies)}</worldbody></mujoco>'''
        model=mujoco.MjModel.from_xml_string(xml)
        data=mujoco.MjData(model)
        ids={pid:mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_BODY,name) for pid,name in body_names.items()}
        for pid,bid in ids.items():
            if self.parts[pid].get('fixed',False):continue
            j=model.body_jntadr[bid];q=model.jnt_qposadr[j];v=model.jnt_dofadr[j]
            data.qpos[q:q+3]=poses[pid]['position'];data.qpos[q+3:q+7]=poses[pid]['quaternion']
            data.qvel[v:v+6]=poses[pid].get('velocity',[0.]*6)
        mujoco.mj_forward(model,data)
        geom_ids={mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_GEOM,name):pid for name,pid in geom_part.items()}
        geom_ids[mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_GEOM,'floor')]='__floor__'
        return model,data,ids,geom_ids

    def _poses_from(self,model,data,ids):
        result={}
        for pid,bid in ids.items():
            vel=[0.]*6
            if not self.parts[pid].get('fixed',False):
                j=model.body_jntadr[bid];v=model.jnt_dofadr[j];vel=data.qvel[v:v+6].tolist()
            result[pid]={'position':data.xpos[bid].tolist(),'quaternion':data.xquat[bid].tolist(),'velocity':vel}
        return result

    def _record_frame(self,label,poses=None,remaining=None,advance=0.):
        if not self.capture:return
        self.clock+=advance
        poses=self.poses if poses is None else poses
        remaining=self.remaining if remaining is None else list(remaining)
        phase='settle' if label.startswith('MuJoCo') else ('extraction' if label.startswith('기하학') else 'initial')
        self.frames.append({'time':round(self.clock,5),'label':label,'phase':phase,
                            'poses':{pid:{'position':poses[pid]['position'],
                                          'quaternion':[*poses[pid]['quaternion'][1:],poses[pid]['quaternion'][0]]} for pid in remaining},
                            'removed':[pid for pid in self.parts if pid not in remaining]})

    def settle(self,remaining=None,poses=None,gravity=None,friction=None,capture=False):
        remaining=self.remaining if remaining is None else list(remaining)
        poses=copy.deepcopy(self.poses if poses is None else poses)
        model,data,ids,geomids=self._build(remaining,poses,gravity,friction)
        peak_d=peak_a=peak_pen=0.;worst=[];steps=round(self.physics['settle_seconds']/self.physics['timestep'])
        for step in range(steps):
            mujoco.mj_step(model,data)
            if step%10==0 or step==steps-1:
                for pid,bid in ids.items():
                    if self.parts[pid].get('fixed',False):continue
                    d=float(np.linalg.norm(data.xpos[bid]-poses[pid]['position']))
                    a=angle_degrees(data.xquat[bid],poses[pid]['quaternion'])
                    peak_d=max(peak_d,d);peak_a=max(peak_a,a)
                    if (d>self.physics['stable_translation_m'] or a>self.physics['stable_rotation_deg']) and pid not in worst:worst.append(pid)
                for contact in data.contact:
                    peak_pen=max(peak_pen,-float(contact.dist))
                if capture:self._record_frame('MuJoCo: 제거 후 중력·마찰 계산',self._poses_from(model,data,ids),remaining,advance=.02)
        mujoco.mj_forward(model,data)
        final=self._poses_from(model,data,ids)
        speed=max([np.linalg.norm(v['velocity'][:3]) for k,v in final.items() if not self.parts[k].get('fixed',False)]+[0.])
        finite=all(np.all(np.isfinite(v['position']+v['quaternion']+v['velocity'])) for v in final.values())
        stable=(finite and peak_pen<=self.physics['stable_penetration_m'] and peak_d<=self.physics['stable_translation_m'] and peak_a<=self.physics['stable_rotation_deg'] and speed<=self.physics['stable_final_speed_m_s'])
        return {'stable':bool(stable),'max_displacement_m':peak_d,'max_rotation_deg':peak_a,
                'final_max_speed_m_s':float(speed),'max_penetration_m':peak_pen,
                'unstable_parts':worst,'physics_steps':steps,'finite':finite},final

    def check(self,part_id,direction):return self._operation(part_id,direction,False)
    def remove(self,part_id,direction):return self._operation(part_id,direction,True)

    def _operation(self,pid,direction,commit):
        if self.checks>=self.max_checks:raise RuntimeError('checker budget exhausted')
        self.checks+=1;start=time.perf_counter();before=list(self.remaining)
        result={'valid':False,'reason':'','blockers':[],'stability':None,
                'part_id':pid,'direction':direction,'checker_call':self.checks,
                'path_samples':0,'physics_steps':0}
        if not isinstance(pid,str) or not isinstance(direction,str):result['reason']='invalid_arguments'
        elif pid not in self.remaining:result['reason']='unknown_or_removed_part'
        elif self.parts[pid].get('fixed',False):result['reason']='fixed_part'
        elif direction not in self.parts[pid].get('allowed_directions',list(DIRECTIONS)) or direction not in DIRECTIONS:result['reason']='invalid_direction'
        else:
            model,data,ids,geomids=self._build()
            bid=ids[pid];j=model.body_jntadr[bid];q=model.jnt_qposadr[j]
            vector=np.asarray(DIRECTIONS[direction]);axis=int(np.argmax(abs(vector)));sign=int(vector[axis])
            allbounds=np.asarray([self.bounds(p) for p in self.remaining]);pb=self.bounds(pid)
            distance=(allbounds[:,1,axis].max()-pb[0,axis] if sign>0 else pb[1,axis]-allbounds[:,0,axis].min())+.015
            samples=max(1,int(math.ceil(distance/self.physics['path_step_m'])))
            initial=np.asarray(self.poses[pid]['position']);frames=[]
            # MuJoCo uses soft contacts. A settled part can have a small
            # existing penetration. Permit only that exact geom pair to
            # separate, never to deepen by more than the numerical slack.
            initial_penetrations={}
            for contact in data.contact:
                pair=tuple(sorted((int(contact.geom1),int(contact.geom2))))
                initial_penetrations[pair]=max(initial_penetrations.get(pair,0.),-float(contact.dist))
            for index in range(samples+1):
                data.qpos[q:q+3]=initial+vector*distance*index/samples
                mujoco.mj_forward(model,data);result['path_samples']+=1
                blockers=set()
                for contact in data.contact:
                    a,b=geomids.get(int(contact.geom1)),geomids.get(int(contact.geom2))
                    pair=tuple(sorted((int(contact.geom1),int(contact.geom2))))
                    initial_depth=initial_penetrations.get(pair,0.)
                    permitted=max(self.physics['penetration_tolerance_m'],initial_depth+self.physics['resting_contact_slack_m'])
                    if initial_depth>self.physics['stable_penetration_m']:
                        permitted=self.physics['penetration_tolerance_m']
                    if pid in (a,b) and contact.dist < -permitted:
                        other=b if a==pid else a
                        if other is not None and other!=pid:blockers.add(other)
                if blockers:
                    result.update(reason='path_collision',blockers=sorted(blockers),collision_distance_m=float(distance*index/samples));break
                if self.capture and index%max(1,samples//24)==0:
                    poses=copy.deepcopy(self.poses);poses[pid]['position']=data.qpos[q:q+3].tolist();frames.append(poses)
            result['extraction_distance_m']=float(distance)
            if not result['reason']:
                after=[p for p in self.remaining if p!=pid]
                stability,final=self.settle(after,self.poses)
                result.update(stability=stability,physics_steps=stability['physics_steps'],valid=stability['stable'],reason='ok' if stability['stable'] else 'unstable_remainder')
                if result['valid'] and commit:
                    if self.capture:
                        for pose in frames:self._record_frame('기하학 경로 재생: '+pid,pose,before,advance=.03)
                        self.settle(after,self.poses,capture=True)
                    self.remaining=after;self.poses=final
                    self.actions.append({'part_id':pid,'direction':direction,'stability':stability})
                    self._record_frame('제거 승인: '+pid)
        result['elapsed_seconds']=time.perf_counter()-start
        result['committed']=bool(commit and result['valid'])
        record={**copy.deepcopy(result),'operation':'remove' if commit else 'check','remaining_before':before,'remaining_after':list(self.remaining)}
        self.trace.append(record)
        self.events.append({'frame':max(0,len(self.frames)-1),'time':self.clock,'type':result['reason'],'part_id':pid,
                            'message':f'{pid} {direction}: {result["reason"]}'})
        return copy.deepcopy(result)

    def dump_demo(self,path,title=None,summary=None):
        path=Path(path).resolve();path.parent.mkdir(parents=True,exist_ok=True)
        import os
        parts=[{'id':pid,'mesh_url':os.path.relpath(self._path(p['visual_mesh']),path.parent),
                'color':p.get('color',[.3,.6,.7]),'fixed':p.get('fixed',False)} for pid,p in self.parts.items()]
        data={'title':title or self.case['id'],'parts':parts,'target_id':self.case['target_id'],
              'frames':self.frames,'events':self.events,
              'summary':{'success':self.success,'physics':self.physics,'checks':self.checks,
                         'actions':self.actions,'scope':self.snapshot()['scope'],**(summary or {})},
              'provenance':self.case.get('provenance',{})}
        path.write_text(json.dumps(data,ensure_ascii=False,indent=2))
        return path
