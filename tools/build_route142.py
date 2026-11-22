#!/usr/bin/env python3
import csv,io,json,os,sys,urllib.request,zipfile
from collections import Counter,defaultdict
from pathlib import Path
URL='https://gtfs.mot.gov.il/gtfsfiles/israel-public-transportation.zip'
def rows(z,name):
 with z.open(name) as f: yield from csv.DictReader(io.TextIOWrapper(f,encoding='utf-8-sig',newline=''))
def main():
 source=sys.argv[1] if len(sys.argv)>1 else '/tmp/octobus-gtfs.zip'
 if not os.path.isfile(source): urllib.request.urlretrieve(URL,source)
 with zipfile.ZipFile(source) as z:
  agencies={r['agency_id']:r.get('agency_name','') for r in rows(z,'agency.txt')}
  ids={r['route_id'] for r in rows(z,'routes.txt') if r.get('route_short_name','').strip()=='142' and agencies.get(r.get('agency_id',''),'').strip()=='דן'}
  if not ids: raise ValueError('Dan 142 not found')
  trips={r['trip_id']:r for r in rows(z,'trips.txt') if r.get('route_id') in ids and r.get('shape_id')}
  trip_stops=defaultdict(list)
  for r in rows(z,'stop_times.txt'):
   if r['trip_id'] in trips: trip_stops[r['trip_id']].append((int(r['stop_sequence']),r['stop_id']))
  stop_ids={sid for values in trip_stops.values() for _,sid in values}
  stops={r['stop_id']:r for r in rows(z,'stops.txt') if r['stop_id'] in stop_ids}
  groups=defaultdict(list)
  for tid,values in trip_stops.items():
   seq=tuple(sid for _,sid in sorted(values))
   if len(seq)<20: continue
   first=stops.get(seq[0],{}).get('stop_name','')
   last=stops.get(seq[-1],{}).get('stop_name','')
   if 'בית העלמין' in first and 'עתידים' in last: key='outbound'
   elif 'עתידים' in first and 'בית העלמין' in last: key='inbound'
   else: continue
   groups[key].append((tid,seq))
  if set(groups)!={'outbound','inbound'}: raise ValueError('Both directions not found')
  selected={}
  for key,values in groups.items():
   seq,count=Counter(seq for _,seq in values).most_common(1)[0]
   tids=[tid for tid,pattern in values if pattern==seq]
   shape_id=Counter(trips[tid]['shape_id'] for tid in tids).most_common(1)[0][0]
   selected[key]=(seq,shape_id,count)
  wanted={v[1] for v in selected.values()}
  geometry=defaultdict(list)
  for r in rows(z,'shapes.txt'):
   if r['shape_id'] in wanted:
    geometry[r['shape_id']].append((int(r['shape_pt_sequence']),float(r['shape_pt_lat']),float(r['shape_pt_lon'])))
  out=Path('driver/82/routes');out.mkdir(parents=True,exist_ok=True)
  from math import hypot
  for direction,(seq,shape_id,count) in selected.items():
   shape=[[lat,lon] for _,lat,lon in sorted(geometry[shape_id])]
   points=[{'code':stops[sid].get('stop_code') or sid,'name':stops[sid]['stop_name'],'lat':float(stops[sid]['stop_lat']),'lon':float(stops[sid]['stop_lon'])} for sid in seq]
   if len(shape)<10 or len(points)<20: raise ValueError('Incomplete GTFS route')
   def distance(a,b): return hypot((a[0]-b[0])*111000,(a[1]-b[1])*95000)
   if distance(shape[0],(points[0]['lat'],points[0]['lon']))>1500 or distance(shape[-1],(points[-1]['lat'],points[-1]['lon']))>1500: raise ValueError('Shape does not match terminal stops')
   pkg={'route_id':'142','direction':direction,'approved':True,'source':URL,'shape_id':shape_id,'stops':points,'geometry':shape}
   (out/(direction+'.json')).write_text(json.dumps(pkg,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
   print(direction,len(points),'stops',len(shape),'shape points',count,'trips')
if __name__=='__main__': main()
