// Generation waits for verified models; scripts and family profiles stay usable.
(()=>{
 const status=document.createElement('p');status.id='startup-status';status.setAttribute('role','status');document.querySelector('header').after(status);
 let busy=false;
 async function update(){
  if(busy||!token)return;busy=true;
  try{
   const state=await api('/startup');status.textContent=state.ready?'':state.failed?'Voice engine needs attention: '+state.message:state.message;status.hidden=state.ready;
   for(const id of ['generate-speech','legacy-generate-speech','generate-batch','short-preview','audition-settings','compare-engines','unload-engine']){const button=document.getElementById(id);if(button){if(!state.ready){button.dataset.startupLock='1';button.disabled=true;}else if(button.dataset.startupLock==='1'){delete button.dataset.startupLock;button.disabled=false;}}}
  }catch(error){status.textContent='Connecting to your local voice engine…';}finally{busy=false;}
 }
 setInterval(update,500);update();
})();
