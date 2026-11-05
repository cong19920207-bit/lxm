"""A finite catalog of implemented contributions, never an executable script field."""
STEPS={
    'player_pass':{'actor':'player','action':'delivery','completion':'valid_drop','label':'你来递球'},
    'xiaomeng_receive':{'actor':'xiaomeng','action':'hand','completion':'rule_execution','label':'小梦接应'},
    'dog_response':{'actor':'dog','action':'dog','completion':'rule_execution','label':'狗狗回应'},
}
STAGES=('puppy','growing','adult')

def joint_reason(rules,values,*,stage='puppy',occupied=False,origin='user',invite_elapsed=float('inf')):
    c=rules['joint']
    if not c['enabled']:return 'joint_disabled'
    if stage not in c.get('allowed_stages',STAGES):return 'stage_not_allowed'
    if origin=='invitation' and c.get('entry','user_and_invite')=='user':return 'invitation_disabled'
    if occupied:return 'pet_busy'
    if values['energy']<c['min_energy']:return 'low_energy'
    if origin=='invitation' and invite_elapsed<c['invite_cooldown_seconds']:return 'invite_cooldown'
    return None
