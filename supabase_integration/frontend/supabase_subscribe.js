 import { createClient } from '@supabase/supabase-js'
 const SUPABASE_URL = process.env.SUPABASE_URL
 const SUPABASE_ANON_KEY = process.env.SUPABASE_ANON_KEY || process.env.NETLIFY_SUPABASE_ANON_KEY
 export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY)
 
 export function subscribeToSignals(onInsert){
   const ch = supabase.channel('public:signals')
     .on('postgres_changes', { event:'INSERT', schema:'public', table:'signals'}, (p)=> onInsert(p.new))
     .subscribe()
   return ch
 }
 export function subscribeToSnapshots(onInsert){
   const ch = supabase.channel('public:snapshots')
     .on('postgres_changes', { event:'INSERT', schema:'public', table:'snapshots'}, (p)=> onInsert(p.new))
     .subscribe()
   return ch
 }