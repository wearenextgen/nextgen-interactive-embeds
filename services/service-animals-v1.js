/* Next Gen: enhance only the eight existing native /services icon blocks.
   No typography, copy, grid placement or other page sections are changed.
   Removing the single page-header script tag restores the native originals. */
(() => {
  'use strict';
  if (!/^\/services\/?$/.test(location.pathname)) return;
  if (window.__ngServiceAnimalsV1) return;
  window.__ngServiceAnimalsV1 = true;
  const base = 'https://wearenextgen.github.io/nextgen-interactive-embeds/assets/service-animals-v1/';
  const entries = [
    ['block-yui_3_17_2_1_1773684282839_32311','music-snail','/music-production-sonic-creatio','Music Production & Sonic Creation'],
    ['block-f160028f8b510b08d13e','visual-chameleon','/visual-design','Visual Design & Creative Direction'],
    ['block-781385f2f71221de1573','motion-rabbit','/motion-design-video-creation','Motion Design & Video Creation'],
    ['block-cdb5863e1fb7a8958552','interactive-crab','/interactive-design','Interactive Design'],
    ['block-d80c4fd3c025548f3936','web-clam','/web-design','Web Design & Digital Platforms'],
    ['block-f5eb7e0151fba49f51c6','social-pigeon','/social-growth-strategy','Social Growth & Strategy'],
    ['block-79e80de79b5898860bf1','3d-beetle','/3d-design-printing','3D Design & Printing'],
    ['block-0bf894ded1bb05033b6a','consulting-owl','/consulting','Creative Consulting']
  ];
  const media = matchMedia('(prefers-reduced-motion: reduce)');
  const style = document.createElement('style');
  style.textContent = `
    .ng-service-animal-ready > .sqs-block-content { position:relative; }
    .ng-service-animal-ready > .sqs-block-content > .fluid-image-component-root { visibility:hidden; pointer-events:none; }
    .ng-service-animal-link { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; border:0!important; background:none; border-radius:6px; }
    .ng-service-animal-link img { display:block; width:100%; height:100%; max-width:100%; max-height:100%; object-fit:contain!important; object-position:center; border:0; }
    .ng-service-animal-link:focus-visible { outline:2px solid #c68cff; outline-offset:3px; }
    .ng-service-animal-link:hover img { filter:drop-shadow(0 0 5px rgba(129,21,255,.4)); }
    @media(prefers-reduced-motion:reduce){.ng-service-animal-link:hover img{filter:none}}
  `;
  document.head.append(style);
  function install([id,name,href,label]) {
    const block = document.getElementById(id);
    if (!block || block.dataset.ngAnimalInstalling) return;
    const content = block.querySelector('.sqs-block-content');
    const original = content?.querySelector('.fluid-image-component-root');
    if (!content || !original) return;
    block.dataset.ngAnimalInstalling = name;
    const link = document.createElement('a');
    link.className = 'ng-service-animal-link'; link.href = href;
    link.setAttribute('aria-label',label); link.title = label;
    const img = new Image(); img.alt = ''; img.decoding = 'async';
    const poster = base+name+'-poster.webp', animated=base+name+'-animation.webp';
    let active=false, visible=false, timer;
    function still(){ clearTimeout(timer); if(img.getAttribute('src')!==poster) img.src=poster; }
    function play(){ if(media.matches || !visible || document.hidden) return still(); if(img.getAttribute('src')!==animated) img.src=animated; }
    function briefly(){play();clearTimeout(timer);timer=setTimeout(()=>{if(!active)still();},4500);}
    link.addEventListener('pointerenter',()=>{active=true;play();});
    link.addEventListener('pointerleave',()=>{active=link.matches(':focus-visible');if(!active)still();});
    link.addEventListener('focus',()=>{active=true;play();});
    link.addEventListener('blur',()=>{active=false;still();});
    media.addEventListener('change',()=>{if(media.matches)still();else if(active)play();});
    document.addEventListener('visibilitychange',()=>{if(document.hidden)still();else if(visible)briefly();});
    img.addEventListener('error',()=>{if(img.getAttribute('src')===animated)still();else{link.remove();block.classList.remove('ng-service-animal-ready');original.removeAttribute('aria-hidden');original.removeAttribute('inert');}});
    img.addEventListener('load',()=>{
      if(block.classList.contains('ng-service-animal-ready'))return;
      link.append(img);content.append(link);
      original.setAttribute('aria-hidden','true');original.setAttribute('inert','');
      block.classList.add('ng-service-animal-ready');
      const observer=new IntersectionObserver(changes=>{for(const change of changes){visible=change.isIntersecting;if(visible)briefly();else still();}},{threshold:.15});
      observer.observe(block);
    },{once:true});
    img.src=poster;
  }
  function run(){entries.forEach(install);}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',run,{once:true});else run();
  window.addEventListener('load',run,{once:true});
  document.addEventListener('mercury:load',run);
})();
