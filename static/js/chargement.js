// static/js/chargement.js : sur toutes les pages du site.
// - Une barre de chargement en haut de la page au lieu d'un écran blanc.
// - Un bouton « Envoyer » ne peut être cliqué qu'une fois (pas de double envoi).
// - Un fichier trop lourd est signalé avant l'envoi (data-taille-max-mo sur le champ).
// - Un avertissement si la connexion est lente ou coupée, et le bouton redevient
//   utilisable pour réessayer.
(function () {
    "use strict";
    var racine = document.documentElement;
    var barre = document.createElement("div");
    barre.className = "barre-chargement";
    barre.setAttribute("aria-hidden", "true");
    var minuterie = null;

    function avertir(texte, avecReessayer) {
        var ancien = document.querySelector(".avertissement-reseau");
        if (ancien) { ancien.remove(); }
        var boite = document.createElement("div");
        boite.className = "avertissement-reseau";
        boite.setAttribute("role", "alert");
        boite.textContent = texte;
        if (avecReessayer) {
            var bouton = document.createElement("button");
            bouton.type = "button";
            bouton.textContent = "Recharger";
            bouton.addEventListener("click", function () { location.reload(); });
            boite.appendChild(bouton);
        }
        var fermer = document.createElement("button");
        fermer.type = "button";
        fermer.textContent = "Fermer";
        fermer.addEventListener("click", function () { boite.remove(); });
        boite.appendChild(fermer);
        document.body.appendChild(boite);
    }

    function boutonsDe(formulaire) {
        return formulaire.querySelectorAll("button[type=submit], button:not([type]), input[type=submit]");
    }

    function rendreLesBoutons() {
        document.querySelectorAll(".en-cours").forEach(function (b) {
            b.disabled = false;
            b.classList.remove("en-cours");
        });
        document.querySelectorAll("form[data-envoye]").forEach(function (f) { delete f.dataset.envoye; });
    }

    function arreter() {
        racine.classList.remove("en-chargement");
        clearTimeout(minuterie);
    }

    function demarrer() {
        if (!barre.isConnected) { document.body.appendChild(barre); }
        // Laisser le navigateur poser la barre à 0 avant de la faire avancer
        requestAnimationFrame(function () { racine.classList.add("en-chargement"); });
        clearTimeout(minuterie);
        // Après 20 secondes, la page n'est toujours pas arrivée : on le dit, et on permet de réessayer
        minuterie = setTimeout(function () {
            arreter();
            rendreLesBoutons();
            avertir(navigator.onLine === false
                ? "Pas de connexion Internet. Vérifiez le réseau puis réessayez."
                : "La connexion est lente : la page met du temps à répondre. Patientez ou réessayez.", false);
        }, 20000);
    }

    // Un lien vers une autre page du site
    document.addEventListener("click", function (e) {
        var lien = e.target.closest && e.target.closest("a[href]");
        if (!lien || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) { return; }
        if (lien.target || lien.hasAttribute("download") || lien.hasAttribute("data-sans-chargement")) { return; }
        if (lien.origin !== location.origin) { return; }
        if (lien.pathname === location.pathname && lien.search === location.search && lien.hash) { return; }
        // Un lien géré par un autre script (visionneuse de photos...) n'ouvre pas de page ;
        // la flèche de retour, elle, change bien de page.
        if (lien.id === "fleche-retour") { demarrer(); return; }
        if (e.defaultPrevented) { return; }
        setTimeout(function () { if (!e.defaultPrevented) { demarrer(); } }, 0);
    });

    // Un formulaire envoyé : un seul envoi, et la barre de chargement
    document.addEventListener("submit", function (e) {
        var formulaire = e.target;
        if (e.defaultPrevented || (formulaire.getAttribute("method") || "").toLowerCase() === "dialog") { return; }
        if (formulaire.dataset.envoye === "1") {
            e.preventDefault();   // deuxième clic : ignoré
            return;
        }
        formulaire.dataset.envoye = "1";
        var clique = e.submitter;
        // Désactiver juste après l'envoi, pour que le bouton cliqué (son name/value) parte avec le formulaire
        setTimeout(function () {
            boutonsDe(formulaire).forEach(function (b) {
                b.disabled = true;
                if (b === clique || (!clique && b.type === "submit")) { b.classList.add("en-cours"); }
            });
        }, 0);
        if (!formulaire.target) { demarrer(); }
    });

    // Fichier trop lourd : prévenu tout de suite, sans attendre l'envoi
    document.addEventListener("change", function (e) {
        var champ = e.target;
        if (champ.type !== "file" || !champ.dataset.tailleMaxMo) { return; }
        var max = parseFloat(champ.dataset.tailleMaxMo) * 1024 * 1024;
        var tropLourds = Array.prototype.filter.call(champ.files || [], function (f) { return f.size > max; });
        var nombreMax = parseInt(champ.dataset.nombreMax || "0", 10);
        if (nombreMax && champ.files.length > nombreMax) {
            champ.setCustomValidity(nombreMax + " fichiers au plus à la fois : envoyez les autres ensuite.");
            champ.reportValidity();
        } else if (tropLourds.length) {
            var noms = tropLourds.map(function (f) { return "« " + f.name + " »"; }).join(", ");
            champ.setCustomValidity("Trop lourd : " + noms + " (" + champ.dataset.tailleMaxMo + " Mo au plus par fichier).");
            champ.reportValidity();
        } else {
            champ.setCustomValidity("");
        }
    });

    // Retour arrière du navigateur : la page revient de la mémoire, tout doit redevenir utilisable
    window.addEventListener("pageshow", function (e) {
        arreter();
        if (e.persisted) { rendreLesBoutons(); }
    });
    window.addEventListener("offline", function () {
        avertir("Pas de connexion Internet. Ce que vous envoyez maintenant ne partira pas.", false);
    });
    window.addEventListener("online", function () {
        var ancien = document.querySelector(".avertissement-reseau");
        if (ancien) { ancien.remove(); }
    });
})();
