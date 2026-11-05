"""Versionable fixed copy; values come from facts or explicit simulation inputs."""
TEMPLATES={'welcome':'{pet_name}，欢迎回家。','fallback':'{pet_name}安静地看着你。','touch':'它把头轻轻留在你的手边。','feed':'它低下头，认真吃起了食物。','play':'它追着小球，摇起了尾巴。','joint_ball':'你和小梦一起陪它玩了一次球。','joint_photo':'这一刻，已经收进共同事件册。','refuse_feed':'它闻了闻，已经吃饱啦。','low_energy':'它有点累了，可以轻轻摸摸它。','touch_incomplete':'这次还没摸够，可以再试试。','rest':'这次先休息。','invite':'邀请小梦玩球','preference_learning':'实际反应证据不足，仍在了解中。','birthday':'今天是{pet_name}的生日纪念日。','return_welcome':'回来啦，来看看它。','return_facts':'这段时间的真实经历，已经留在记录里。','return_empty':'回来陪陪它就好。'}
def render(ai,key,**values):
 from backend.services.pet_expression import render_template
 return render_template((ai or {}).get('templates',{}).get(key,TEMPLATES[key]),values)
