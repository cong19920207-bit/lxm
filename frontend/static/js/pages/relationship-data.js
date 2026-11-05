// Relationship timestamps in storage are UTC, including legacy strings without an offset.
export function parseRelationshipTime(value) {
  if (!value) return null;
  const text=String(value), date=new Date(/(?:Z|[+-]\d{2}:?\d{2})$/i.test(text)?text:text+'Z');
  return Number.isFinite(date.getTime())?date:null;
}
export function beijingDay(value) {
  const date=value instanceof Date?value:parseRelationshipTime(value);
  return date?new Date(date.getTime()+8*3600000).toISOString().slice(0,10):'';
}
export function recentLogWindow(now=new Date()) {
  const day=beijingDay(now), start=Date.parse(day+'T00:00:00+08:00')-6*86400000;
  return {start,end:start+7*86400000};
}
export function visibleRecentLogs(items,window=recentLogWindow()) {
  return items.filter(item=>{
    const date=parseRelationshipTime(item.created_at);
    return date&&date.getTime()>=window.start&&date.getTime()<window.end;
  });
}
