"""Independent DeepSeek HTTP adapter: frozen env config, one post, bounded total time."""
import asyncio,json,math,os,time
from dataclasses import dataclass,field
from functools import lru_cache
from hashlib import sha256
from urllib.parse import urlsplit
import httpx
from datetime import datetime
from backend.services.pet_user_service import now_utc
from backend.services.pet_settlement import aware
from backend.constants import DEEPSEEK_DEFAULT_MODEL

class ModelConfigurationError(ValueError):pass
class ProviderFailure(ValueError):
 def __init__(self,reason,result):super().__init__(reason);self.reason=reason;self.result=result

@dataclass(frozen=True)
class ModelConfig:
 base_url:str
 model:str
 api_key:str=field(repr=False)
 timeout_seconds:float=90
 source:str="server_env"
 @classmethod
 def from_env(cls,env=None):
  env=os.environ if env is None else env
  # Reuse the existing DeepSeek deployment by default. Explicit legacy pet overrides remain supported.
  url=env.get('PET_LLM_BASE_URL',env.get('DEEPSEEK_BASE_URL','') or 'https://api.deepseek.com').strip().rstrip('/')
  model=env.get('PET_LLM_MODEL',DEEPSEEK_DEFAULT_MODEL).strip()
  key=env.get('PET_LLM_API_KEY',env.get('DEEPSEEK_API_KEY','')).strip()
  parsed=urlsplit(url)
  if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:raise ModelConfigurationError(('PET_LLM_BASE_URL' if 'PET_LLM_BASE_URL' in env else 'DEEPSEEK_BASE_URL')+'_invalid')
  if parsed.hostname!='api.deepseek.com' or parsed.path not in {'','/v1'}:raise ModelConfigurationError('PET_LLM_provider_not_verified')
  if model not in {'deepseek-flash','deepseek-v4-pro'}:raise ModelConfigurationError('PET_LLM_MODEL_invalid_or_unsupported')
  if not key or any(c.isspace() for c in key):raise ModelConfigurationError(('PET_LLM_API_KEY' if 'PET_LLM_API_KEY' in env else 'DEEPSEEK_API_KEY')+'_missing_or_invalid')
  try:timeout=float(env.get('PET_LLM_TIMEOUT_SECONDS','90'))
  except (TypeError,ValueError):raise ModelConfigurationError('PET_LLM_TIMEOUT_SECONDS_invalid')
  if not math.isfinite(timeout) or not .1<=timeout<=300:raise ModelConfigurationError('PET_LLM_TIMEOUT_SECONDS_must_be_0.1_to_300')
  return cls(url,model,key,timeout,source='pet_override' if any(k in env for k in ('PET_LLM_BASE_URL','PET_LLM_MODEL','PET_LLM_API_KEY')) else 'shared_deepseek')
 def public(self):
  value={'base_url':self.base_url,'model':self.model,'timeout_seconds':self.timeout_seconds,'credential_configured':bool(self.api_key),'source':self.source,'activation':'process_restart'}
  value['configuration_id']=sha256((json.dumps(value,sort_keys=True)+self.api_key).encode()).hexdigest();return value

@lru_cache(maxsize=1)
def deployment_config():return ModelConfig.from_env()

def resolve_thinking(global_value='default',workflow_value='inherit'):
 if global_value not in {'default','on','off'} or workflow_value not in {'inherit','on','off'}:raise ModelConfigurationError('thinking_combination_invalid')
 effective=global_value if workflow_value=='inherit' else workflow_value
 return {'global':global_value,'workflow':workflow_value,'resolved':effective,'source':'workflow' if workflow_value!='inherit' else 'provider_default' if effective=='default' else 'pet_global',
  'parameter':None if effective=='default' else {'type':'enabled' if effective=='on' else 'disabled'}}

def status(ai=None):
 ai=ai or {};workflows={}
 try:
  for kind in ('immediate','daily','period','return'):workflows[kind]=resolve_thinking(ai.get('thinking','default'),ai.get('workflow_thinking',{}).get(kind,'inherit'))
  config=deployment_config();return {'available':True,'configuration':config.public(),'workflows':workflows,'problems':[]}
 except ModelConfigurationError as error:return {'available':False,'configuration':{'source':'server_env','credential':'not_returned'},'workflows':workflows,'problems':[str(error)],'template_available':True}

def usage_of(raw):
 raw=raw if isinstance(raw,dict) else {}
 number=lambda x:x if type(x) is int and x>=0 else None
 details=raw.get('completion_tokens_details') or {}
 usage={'input_tokens':number(raw.get('prompt_tokens')),'output_tokens':number(raw.get('completion_tokens')),'reasoning_tokens':number(details.get('reasoning_tokens') if isinstance(details,dict) else None)}
 usage['complete']=usage['input_tokens'] is not None and usage['output_tokens'] is not None
 return usage

async def send_once(config,messages,thinking,*,transport=None,deadline=None,clock=now_utc):
 if isinstance(deadline,str):deadline=datetime.fromisoformat(deadline)
 start=time.monotonic();result={'configuration':config.public(),'thinking':thinking,'usage':usage_of(None),'returned_model':None,'elapsed_ms':0}
 if deadline and clock()>=aware(deadline):raise ProviderFailure('claim_expired_before_transport',result)
 body={'model':config.model,'messages':messages,'stream':False,'response_format':{'type':'json_object'}}
 if thinking['parameter'] is not None:body['thinking']=thinking['parameter']
 try:
  async with asyncio.timeout(config.timeout_seconds):
   async with httpx.AsyncClient(timeout=httpx.Timeout(config.timeout_seconds),transport=transport,follow_redirects=False,trust_env=False) as client:
    if deadline and clock()>=aware(deadline):raise ProviderFailure('claim_expired_before_transport',result)
    # A 200 header can precede a long generation/body stall. Preserve it even
    # when the bounded read times out; headers alone do not prove completion.
    async with client.stream('POST',config.base_url+'/chat/completions',headers={'Authorization':'Bearer '+config.api_key},json=body) as response:
     result['http_status']=response.status_code
     if response.status_code!=200:raise ProviderFailure('provider_http_'+str(response.status_code),result)
     await response.aread()
     raw=response.json()
    if not isinstance(raw,dict):raise ValueError('response_object_required')
    result['returned_model']=raw.get('model');result['usage']=usage_of(raw.get('usage'))
    result['content']=raw['choices'][0]['message']['content']
    if not isinstance(result['content'],str):raise ValueError()
    result['finish_reason']=raw['choices'][0].get('finish_reason')
 except (TimeoutError,httpx.TimeoutException,httpx.RequestError) as error:
  result['failure']={'phase':'transport','kind':'timeout' if isinstance(error,(TimeoutError,httpx.TimeoutException)) else 'connection'}
  raise ProviderFailure('send_unknown',result)
 except (KeyError,IndexError,ValueError,TypeError) as error:
  if isinstance(error,ProviderFailure):raise
  raise ProviderFailure('provider_response_invalid',result)
 finally:result['elapsed_ms']=round((time.monotonic()-start)*1000,2)
 return result

async def execute_claim(sessions,c,messages,*,config=None,transport=None,clock=now_utc,writer=None):
 from backend.models.pet_generation import PetGenerationTask
 from backend.services.pet_generation import permit,commit_result,transport_authorized
 if not c:return {'ok':False,'reason':'not_claimed'}
 async with sessions() as db:
  t=await db.get(PetGenerationTask,c['task_id']);ai=t.configuration.get('ai',{});kind=t.kind
 try:
  config=config or deployment_config();thinking=resolve_thinking(ai.get('thinking','default'),ai.get('workflow_thinking',{}).get(kind,'inherit'))
 except ModelConfigurationError as error:
  await permit(sessions,c,now=clock(),configuration_error=str(error));return {'ok':False,'reason':str(error)}
 if not await permit(sessions,c,now=clock(),model_snapshot={**config.public(),'thinking':thinking}):return {'ok':False,'reason':'send_not_authorized'}
 receipt={'configuration':config.public(),'thinking':thinking,'usage':usage_of(None),'returned_model':None}
 phase='pre_transport'
 try:
  if not await transport_authorized(sessions,c,now=clock()):return {'ok':False,'reason':'stale_before_transport'}
  phase='transport'
  receipt=await send_once(config,messages,thinking,transport=transport,deadline=c['lease_until'],clock=clock)
  phase='result_commit'
  accepted=await commit_result(sessions,c,receipt,now=clock(),writer=writer)
  return {'ok':accepted,'result':receipt,'reason':None if accepted else 'stale_result'}
 except ProviderFailure as error:
  await commit_result(sessions,c,error.result,now=clock(),error=error.reason)
  return {'ok':False,'reason':error.reason}
 except asyncio.CancelledError:
  receipt={**receipt,'failure':{'phase':phase,'kind':'cancelled'}}
  await asyncio.shield(commit_result(sessions,c,receipt,now=clock(),error='execution_cancelled'))
  raise
 except Exception as error:
  receipt={**receipt,'failure':{'phase':phase,'kind':type(error).__name__}}
  args=getattr(getattr(error,'orig',None),'args',())
  if args and type(args[0]) is int:receipt['database_code']=args[0]
  await commit_result(sessions,c,receipt,now=clock(),error='execution_error')
  raise
