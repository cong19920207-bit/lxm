"""Side-effect-free decisions shared by execution and administration previews."""
def action_reason(rules,values,action,*,occupied=False,duration_ms=None):
    if occupied:return 'pet_busy'
    interaction=rules['interaction']
    if action=='feed' and values['satiety']>=interaction['feed_max_satiety']:return 'already_full'
    if action in {'play','joint_ball'}:
        minimum=rules['joint']['min_energy'] if action=='joint_ball' else interaction['play_energy_min']
        if values['energy']<minimum:return 'low_energy'
    if action in {'touch','play'} and duration_ms is not None:
        minimum=interaction['touch_min_seconds' if action=='touch' else 'play_round_seconds']*1000
        if not isinstance(duration_ms,(int,float)) or isinstance(duration_ms,bool) or duration_ms<minimum:return action+'_incomplete'
    return None


def reward(rules,action,*,spent,closeness,same_family=False,cooling=False):
    if same_family:return 0,'parent_already_rewarded'
    if cooling:return 0,'cooldown'
    c=rules['rewards']
    amount=max(0,min(c['amounts'].get(action,0),c['daily_cap']-spent,c['maximum_closeness']-closeness))
    return amount,'rewarded' if amount else 'cap'


def care_reason(rules,values,*,used=0,elapsed_hours=float('inf'),occupied=False):
    if occupied:return 'pet_busy'
    care=rules['care']
    if used>=care['daily_cap']:return 'daily_cap'
    if elapsed_hours<care['min_interval_hours']:return 'care_interval'
    if values['satiety']>=care['feed_threshold']:return 'no_feed_needed'
    return None
