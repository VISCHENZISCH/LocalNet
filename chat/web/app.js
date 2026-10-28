// Client web de LocalNet, servi par le salon : même protocole que l'application de bureau
// (voir chat/protocole.py). Aucune bibliothèque, aucun accès à Internet.
"use strict";

const TAILLE_MORCEAU = 256 * 1024;
const TAILLE_ID = 8;
const FICHIER_MAX = 500 * 1024 * 1024;
const COTE_PHOTO = 256;
const EXTENSIONS = {
  image: [".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"],
  video: [".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v"],
};
const LISIBLES = [".mp4", ".webm", ".mov", ".m4v"]; // vidéos que les navigateurs savent lire
const TEINTES = ["#1877F2", "#42B72A", "#E9710F", "#F3425F", "#9360F7", "#0F9D8F", "#D6308A", "#5C6BC0"];
const ICONE_TELECHARGER = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/></svg>';
const ICONE_LECTURE = '<svg viewBox="0 0 24 24" aria-hidden="true"><polygon points="6 3 20 12 6 21 6 3"/></svg>';

const $ = (id) => document.getElementById(id);

const etat = {
  ws: null,
  pseudo: "",
  mdp: "",          // gardé en mémoire le temps de la session, pour se reconnecter
  nouveau: false,
  entre: false,     // bienvenue reçue au moins une fois
  fatal: false,     // le salon a refusé : pas de reconnexion
  avatars: {},      // pseudo -> id
  dernierAuteur: null,
  file: [],         // fichiers à envoyer
  envoiEnCours: false,
  nonLus: 0,
  colle: true,      // le fil est en bas : on le suit quand un message ou une image arrive
};

// --- Outils -----------------------------------------------------------------

function el(balise, classe, texte) {
  const e = document.createElement(balise);
  if (classe) e.className = classe;
  if (texte !== undefined) e.textContent = texte;
  return e;
}

function extension(nom) {
  const i = nom.lastIndexOf(".");
  return i < 0 ? "" : nom.slice(i).toLowerCase();
}

function genre(nom) {
  const ext = extension(nom);
  return Object.keys(EXTENSIONS).find((g) => EXTENSIONS[g].includes(ext)) || null;
}

function tailleLisible(octets) {
  for (const unite of ["o", "Ko", "Mo"]) {
    if (octets < 1024) return `${Math.round(octets)} ${unite}`;
    octets /= 1024;
  }
  return `${octets.toFixed(1)} Go`;
}

function teinte(pseudo) {
  const somme = new TextEncoder().encode(pseudo.toLowerCase()).reduce((a, b) => a + b, 0);
  return TEINTES[somme % TEINTES.length];
}

function lire(cle) {
  try { return localStorage.getItem(cle) || ""; } catch { return ""; }
}

function ecrire(cle, valeur) {
  try { localStorage.setItem(cle, valeur); } catch { /* navigation privée */ }
}

const pause = (ms) => new Promise((r) => setTimeout(r, ms));

// --- Avatars ----------------------------------------------------------------

function remplirAvatar(span, pseudo) {
  span.dataset.pseudo = pseudo.toLowerCase();
  span.replaceChildren();
  const id = etat.avatars[pseudo.toLowerCase()];
  if (id) {
    const img = el("img");
    img.alt = "";
    img.src = `/avatars/${id}`;
    span.append(img);
    span.style.background = "transparent";
  } else {
    span.textContent = (pseudo[0] || "?").toUpperCase();
    span.style.background = teinte(pseudo);
  }
}

function avatar(pseudo) {
  const span = el("span", "avatar");
  remplirAvatar(span, pseudo);
  return span;
}

function majAvatars(avatars) {
  etat.avatars = {};
  for (const [p, id] of Object.entries(avatars || {})) etat.avatars[p.toLowerCase()] = id;
  document.querySelectorAll(".avatar[data-pseudo]").forEach((span) => remplirAvatar(span, span.dataset.pseudo));
}

// --- Écrans -----------------------------------------------------------------

function afficherConnexion(erreur) {
  $("salon").hidden = true;
  $("connexion").hidden = false;
  $("valider").disabled = false;
  montrerErreur(erreur || "");
  document.title = "LocalNet";
}

function montrerErreur(texte) {
  $("erreur").textContent = texte;
  $("erreur").hidden = !texte;
}

function mode(nouveau) {
  etat.nouveau = nouveau;
  $("onglet-connexion").setAttribute("aria-selected", String(!nouveau));
  $("onglet-creation").setAttribute("aria-selected", String(nouveau));
  $("valider").textContent = nouveau ? "Créer le compte et rejoindre" : "Se connecter";
  $("mdp").placeholder = nouveau ? "Mot de passe (4 caractères min.)" : "Mot de passe";
  $("mdp").autocomplete = nouveau ? "new-password" : "current-password";
  montrerErreur("");
}

// --- Connexion --------------------------------------------------------------

function connecter() {
  const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
  ws.binaryType = "arraybuffer";
  etat.ws = ws;
  etat.fatal = false;
  $("etat").textContent = "connexion…";
  ws.onopen = () => ws.send(JSON.stringify({
    type: "bonjour", pseudo: etat.pseudo, mot_de_passe: etat.mdp, nouveau: etat.nouveau,
  }));
  ws.onmessage = (e) => {
    if (typeof e.data !== "string") return;
    let m;
    try { m = JSON.parse(e.data); } catch { return; }
    if (m && typeof m.type === "string") recevoir(m);
  };
  ws.onclose = () => {
    if (etat.ws !== ws) return; // connexion remplacée ou fermée volontairement
    etat.ws = null;
    if (etat.fatal) return;
    if (!etat.entre) {
      afficherConnexion("Connexion impossible : salon injoignable.");
      return;
    }
    $("etat").textContent = "hors ligne — reconnexion…";
    setTimeout(() => { if (!etat.ws && etat.mdp) connecter(); }, 3000);
  };
}

function quitter() {
  const ws = etat.ws;
  etat.ws = null;
  etat.mdp = "";
  etat.entre = false;
  etat.file = [];
  if (ws) ws.close();
  $("profil").close();
  $("mdp").value = "";
  afficherConnexion("");
}

function recevoir(m) {
  switch (m.type) {
    case "bienvenue":
      etat.pseudo = m.pseudo;
      etat.nouveau = false; // compte créé : les reconnexions sont de simples connexions
      etat.entre = true;
      $("connexion").hidden = true;
      $("salon").hidden = false;
      $("etat").textContent = "en ligne";
      $("mdp").value = "";
      majAvatars(m.avatars);
      remplirAvatar($("mon-avatar"), etat.pseudo);
      // Fil reconstruit depuis l'historique : rien ne manque après une coupure.
      $("fil").replaceChildren();
      etat.dernierAuteur = null;
      (m.historique || []).forEach(afficherElement);
      membres(m.membres);
      defiler(true);
      break;
    case "message":
    case "fichier":
      afficherElement(m);
      if (document.hidden) {
        etat.nonLus += 1;
        document.title = `(${etat.nonLus}) LocalNet`;
      }
      break;
    case "avatars":
      majAvatars(m.avatars);
      break;
    case "arrivee":
    case "depart":
      note(`${m.pseudo} ${m.type === "arrivee" ? "a rejoint" : "a quitté"} le salon`);
      membres(m.membres);
      break;
    case "erreur":
      if (m.fatal) {
        etat.fatal = true;
        etat.mdp = "";
        etat.entre = false;
        afficherConnexion(m.texte || "Connexion refusée.");
      } else {
        note(m.texte || "Erreur");
      }
      break;
  }
}

// --- Fil --------------------------------------------------------------------

function presDuBas() {
  const fil = $("fil");
  return fil.scrollHeight - fil.scrollTop - fil.clientHeight < 160;
}

function defiler(force) {
  if (!force && !etat.colle) return;
  etat.colle = true;
  requestAnimationFrame(() => { $("fil").scrollTop = $("fil").scrollHeight; });
}

function ajouter(contenu, auteur, heure) {
  const suivre = presDuBas();
  const moi = auteur === etat.pseudo;
  const debut = auteur !== etat.dernierAuteur;
  etat.dernierAuteur = auteur;

  const ligne = el("div", `ligne ${moi ? "moi" : "autre"}${debut ? " debut" : ""}`);
  if (!moi) {
    if (debut) {
      const a = avatar(auteur);
      a.title = auteur;
      ligne.append(a);
    } else {
      ligne.append(el("span", "place"));
    }
  }
  const pile = el("div", "pile");
  if (debut && !moi) pile.append(el("span", "auteur", auteur));
  pile.append(contenu);
  if (heure) pile.append(el("span", "heure", heure));
  ligne.append(pile);
  $("fil").append(ligne);
  if (suivre || moi) defiler(true);
}

function note(texte) {
  etat.dernierAuteur = null;
  const suivre = presDuBas();
  $("fil").append(el("p", "note", texte));
  if (suivre) defiler(true);
}

function afficherElement(m) {
  if (m.type === "message") ajouter(el("div", "bulle", m.texte), m.de, m.heure);
  else if (m.type === "fichier") ajouter(blocFichier(m), m.de, m.heure);
}

function blocFichier(m) {
  const url = `/fichiers/${encodeURIComponent(m.id)}`;
  const bloc = el("div", "media");
  const infos = el("div", "infos");
  infos.append(el("strong", "", m.nom));
  const detail = el("span", "petit doux", tailleLisible(m.taille));
  infos.append(detail);
  const indisponible = () => { detail.textContent = "Fichier indisponible"; };

  if (m.genre === "image") {
    const lien = el("a");
    lien.href = url;
    lien.target = "_blank";
    lien.rel = "noopener";
    const img = el("img");
    img.alt = m.nom;
    img.loading = "lazy";
    img.src = url;
    img.addEventListener("load", () => defiler(false)); // l'image agrandit le fil
    img.addEventListener("error", () => { lien.remove(); indisponible(); });
    lien.append(img);
    bloc.append(lien);
  } else if (LISIBLES.includes(extension(m.nom))) {
    const video = el("video");
    video.controls = true;
    video.preload = "metadata";
    video.playsInline = true;
    video.src = url;
    video.addEventListener("error", () => { video.remove(); indisponible(); });
    bloc.append(video);
  } else {
    // mkv, avi : le navigateur ne sait pas les lire, on propose de les télécharger.
    const vignette = el("a", "vignette");
    vignette.href = url;
    vignette.download = m.nom;
    vignette.innerHTML = ICONE_LECTURE;
    vignette.setAttribute("aria-label", `Télécharger ${m.nom}`);
    bloc.append(vignette);
  }

  const pied = el("div", "pied");
  const telecharger = el("a", "icone");
  telecharger.href = url;
  telecharger.download = m.nom;
  telecharger.innerHTML = ICONE_TELECHARGER;
  telecharger.setAttribute("aria-label", `Enregistrer ${m.nom}`);
  pied.append(infos, telecharger);
  bloc.append(pied);
  return bloc;
}

function membres(liste) {
  liste = liste || [];
  $("nb-membres").textContent = String(liste.length);
  const ul = $("liste-membres");
  ul.replaceChildren();
  for (const pseudo of liste) {
    const li = el("li");
    const a = avatar(pseudo);
    a.title = pseudo;
    li.append(a, el("span", "", pseudo + (pseudo === etat.pseudo ? "  (vous)" : "")));
    ul.append(li);
  }
}

// --- Envoi ------------------------------------------------------------------

function envoyerTexte() {
  const champ = $("texte");
  const texte = champ.value.trim();
  if (!texte) return;
  if (!etat.ws || etat.ws.readyState !== WebSocket.OPEN) {
    note("Hors ligne : message non envoyé.");
    return;
  }
  etat.ws.send(JSON.stringify({ type: "message", texte }));
  champ.value = "";
  ajuster();
}

function envoyerFichiers(fichiers) {
  for (const f of fichiers) {
    if (!genre(f.name)) note(`« ${f.name} » ignoré : seules les photos et vidéos sont acceptées.`);
    else if (f.size === 0 || f.size > FICHIER_MAX) note(`« ${f.name} » ignoré : vide ou plus de ${tailleLisible(FICHIER_MAX)}.`);
    else etat.file.push(f);
  }
  if (!etat.envoiEnCours) traiterFile();
}

async function traiterFile() {
  etat.envoiEnCours = true;
  try {
    while (etat.file.length) {
      const f = etat.file.shift();
      try {
        await envoyerFichier(f);
      } catch (e) {
        note(`« ${f.name} » : ${e.message}`);
        etat.file = [];
      }
    }
  } finally {
    etat.envoiEnCours = false;
    $("envoi").hidden = true;
  }
}

async function envoyerFichier(f) {
  const ws = etat.ws;
  const ouverte = () => etat.ws === ws && ws.readyState === WebSocket.OPEN;
  if (!ws || !ouverte()) throw new Error("hors ligne, envoi annulé.");
  const id = Array.from(crypto.getRandomValues(new Uint8Array(TAILLE_ID / 2)),
    (o) => o.toString(16).padStart(2, "0")).join("");
  const prefixe = new TextEncoder().encode(id);
  const progression = (envoye) => {
    $("envoi-barre").value = Math.max(0, Math.min(100, (envoye * 100) / f.size));
  };
  $("envoi").hidden = false;
  $("envoi-nom").textContent = f.name;
  progression(0);

  ws.send(JSON.stringify({ type: "fichier", id, nom: f.name, taille: f.size }));
  let lu = 0;
  while (lu < f.size) {
    while (ws.bufferedAmount > 4 * TAILLE_MORCEAU) { // le fichier n'est jamais entièrement en mémoire
      if (!ouverte()) throw new Error("connexion perdue, envoi annulé.");
      await pause(30);
      progression(lu - ws.bufferedAmount);
    }
    if (!ouverte()) throw new Error("connexion perdue, envoi annulé.");
    const morceau = new Uint8Array(await f.slice(lu, lu + TAILLE_MORCEAU).arrayBuffer());
    const trame = new Uint8Array(TAILLE_ID + morceau.length);
    trame.set(prefixe);
    trame.set(morceau, TAILLE_ID);
    ws.send(trame);
    lu += morceau.length;
    progression(lu - ws.bufferedAmount);
  }
  while (ws.bufferedAmount > 0 && ouverte()) {
    await pause(50);
    progression(lu - ws.bufferedAmount);
  }
}

// --- Photo de profil --------------------------------------------------------

function recadrer(fichier) {
  // Carré central de 256×256 en JPEG, comme l'application de bureau.
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(fichier);
    const img = new Image();
    img.onload = () => {
      URL.revokeObjectURL(url);
      const cote = Math.min(img.naturalWidth, img.naturalHeight);
      const toile = document.createElement("canvas");
      toile.width = toile.height = COTE_PHOTO;
      toile.getContext("2d").drawImage(img, (img.naturalWidth - cote) / 2, (img.naturalHeight - cote) / 2,
        cote, cote, 0, 0, COTE_PHOTO, COTE_PHOTO);
      const donnees = toile.toDataURL("image/jpeg", 0.88);
      resolve(donnees.slice(donnees.indexOf(",") + 1));
    };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error("image illisible")); };
    img.src = url;
  });
}

async function choisirPhoto(fichier) {
  if (!etat.ws) return;
  try {
    const donnees = await recadrer(fichier);
    etat.ws.send(JSON.stringify({ type: "avatar", donnees }));
  } catch (e) {
    note(`Photo de profil : ${e.message}.`);
  }
}

// --- Saisie -----------------------------------------------------------------

function ajuster() {
  const champ = $("texte");
  champ.style.height = "auto";
  champ.style.height = `${Math.min(champ.scrollHeight + 2, 140)}px`;
}

function initialiser() {
  $("hote").textContent = location.hostname;
  $("titre-salon").textContent = `Salon · ${location.hostname}`;
  $("pseudo").value = lire("pseudo");
  mode(!$("pseudo").value);

  $("onglet-connexion").addEventListener("click", () => mode(false));
  $("onglet-creation").addEventListener("click", () => mode(true));
  $("formulaire").addEventListener("submit", (e) => {
    e.preventDefault();
    const pseudo = $("pseudo").value.trim();
    const mdp = $("mdp").value;
    if (!/^[\p{L}\p{N}_.-]{1,20}$/u.test(pseudo)) {
      montrerErreur("Nom d'utilisateur : 1 à 20 caractères (lettres, chiffres, « . », « _ », « - »).");
      return;
    }
    if (mdp.length < 4 || mdp.length > 64) {
      montrerErreur("Le mot de passe doit faire de 4 à 64 caractères.");
      return;
    }
    ecrire("pseudo", pseudo);
    Object.assign(etat, { pseudo, mdp, entre: false });
    $("valider").disabled = true;
    montrerErreur("");
    if (etat.ws) { const ancien = etat.ws; etat.ws = null; ancien.close(); }
    connecter();
  });

  $("fil").addEventListener("scroll", () => { etat.colle = presDuBas(); }, { passive: true });
  $("saisie").addEventListener("submit", (e) => { e.preventDefault(); envoyerTexte(); });
  $("texte").addEventListener("input", ajuster);
  $("texte").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing && matchMedia("(hover: hover)").matches) {
      e.preventDefault(); // sur ordinateur, Entrée envoie ; sur téléphone, le bouton d'envoi s'en charge
      envoyerTexte();
    }
  });
  $("fichiers").addEventListener("change", (e) => {
    envoyerFichiers([...e.target.files]);
    e.target.value = "";
  });
  document.addEventListener("dragover", (e) => { if (etat.entre) e.preventDefault(); });
  document.addEventListener("drop", (e) => {
    if (!etat.entre) return;
    e.preventDefault();
    envoyerFichiers([...e.dataTransfer.files]);
  });

  $("ouvrir-membres").addEventListener("click", () => $("membres").showModal());
  $("ouvrir-profil").addEventListener("click", () => {
    $("profil-nom").textContent = etat.pseudo;
    remplirAvatar($("profil-avatar"), etat.pseudo);
    $("profil").showModal();
  });
  document.querySelectorAll("[data-fermer]").forEach((b) => b.addEventListener("click", () => b.closest("dialog").close()));
  document.querySelectorAll("dialog").forEach((d) => d.addEventListener("click", (e) => {
    if (e.target === d) d.close(); // toucher en dehors ferme la feuille
  }));
  $("photo").addEventListener("change", (e) => {
    if (e.target.files[0]) choisirPhoto(e.target.files[0]);
    e.target.value = "";
  });
  $("retirer-photo").addEventListener("click", () => {
    if (etat.ws) etat.ws.send(JSON.stringify({ type: "avatar", donnees: null }));
  });
  $("quitter").addEventListener("click", quitter);

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) {
      etat.nonLus = 0;
      document.title = "LocalNet";
      // Au retour sur l'onglet (téléphone mis en veille), on se reconnecte tout de suite.
      if (etat.entre && !etat.ws && etat.mdp) connecter();
    }
  });
}

document.addEventListener("DOMContentLoaded", initialiser);
