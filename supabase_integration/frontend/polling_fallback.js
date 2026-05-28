import { createClient } from '@supabase/supabase-js'
 const supabase = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_ANON_KEY)
 async function fetchLatestSignals(){ const { data } = await supabase.from('signals').select('*').order('created_at',{ascending:false}).limit(50); return data; }
 setInterval(async ()=> { const s = await fetchLatestSignals(); window.updateSignalsUI && window.updateSignalsUI(s); }, 900000);
 fetchLatestSignals().then(s=> window.updateSignalsUI && window.updateSignalsUI(s));