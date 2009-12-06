#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8

FAKE_GETTEXT = {
        "en" : {
            "gender-mismatch":"Reported gender '%s' for Child ID %s does not match previously reported gender=%s",
            "dob-mismatch":"Reported date of birth '%s' for Child ID %s does not match previosly reported DOB=%s",
            "register-before-reporting":"Please register before submitting survey: Send the word REGISTER followed by your Interviewer ID and your full name.",
            "too-many-tokens":"Too much data!",
            "invalid-id":"Sorry, ID code '%s' is not valid for a %s",
            "invalid-dob":"Sorry I don't understand '%s' as a child's date of birth. Please use DDMMYY",
            "invalid-gender":"Sorry I don't understand '%s' as a child's gender. Please use M for male or F for female.",
            "invalid-measurement":"Possible measurement error. Please check height, weight, MUAC or age of child.",
            "report-confirm":"Thanks, %s. Received %s",
            "invalid-message":"Sorry, I don't understand.",
            "cancel-confirm":"CANCELLED report submitted by %s (ID %s) on %s for Cluster %s Child ID %s Household %s",
            "cancel-error":"Sorry, unable to locate report for Cluster %s Child ID %s Household %s",
            "register-confirm":"Hello %s, thanks for registering as Interviewer ID %s!",
            "register-again":"Hello again, %s. You are already registered with RapidSMS",
            "remove-confirm":"%s has been removed from Interviewer ID %s"
        },

        "fr" : {
            "gender-mismatch":u"Reported gender '%s' for Child ID %s does not match previously reported gender=%s",
            "dob-mismatch":u"Reported date of birth '%s' for Child ID %s does not match previosly reported DOB=%s",
            "register-before-reporting":u"Enregistrez l\'apareil SVP",
            "too-many-tokens":u"Le format n\'est pas bon, Revisez SVP",
            "invalid-id":u"Le code '%s' n\'est pas bon pour %s",
            "invalid-dob":u"La date'%s' n\'est pas bonne. Utilisez JJMMAA SVP.",
            "invalid-gender":u"La réponse '%s' n\'est pas bonne pour sexe d\'enfant. Utilisez M ou F SVP.",
            "invalid-measurement":u"Verifiez l\'âge et mesures et renvoyer SVP.",
            "report-confirm":u"Merci, %s. Bien reçu %s",
            "invalid-message":u"Format d\'envoi non valide.",
            "cancel-confirm":u"ANNULÉ données %s (ID %s) sur %s ID Cluster %s Enfant %s Household %s,",
            "cancel-error":u"Verifiez ID enfant et renvoyer SVP - ID Cluster %s Enfant %s Household %s",
            "register-confirm":u"Bonjour %s, Vous êtes enregistré avec le número d\'ID %s!",
            "register-again":u"Salut, %s. Vous êtes enregistré deja avec RapidSMS",
            "remove-confirm":u"%s a été enlevé du número d\'ID %s"
        }
    }
