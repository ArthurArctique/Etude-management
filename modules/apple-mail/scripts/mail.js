// Client Apple Mail pour agents (Claude Code, Codex) — JXA, sortie JSON.
// Lecture libre. move, trash et send renvoient un aperçu et n'agissent qu'avec --confirm.
// draft ouvre une fenêtre de rédaction visible et n'envoie jamais rien.
// Aucune commande ne supprime définitivement un message ni ne vide une corbeille.
ObjC.import('Foundation');

const FLAGS = new Set(['confirm', 'unread-only', 'content', 'read', 'unread', 'flag', 'unflag']);
const MULTI = new Set(['to', 'cc', 'bcc', 'attach']);
const INBOX_NAMES = ['inbox', 'boîte de réception', 'boite de reception'];

function run(argv) {
  let result;
  try {
    const [command, ...rest] = argv;
    const handler = COMMANDS[command];
    if (!handler) {
      throw new Error(`Commande inconnue : ${command || '(aucune)'}. Commandes : ${Object.keys(COMMANDS).join(', ')}`);
    }
    result = handler(parseArgs(rest));
  } catch (e) {
    const message = String(e && e.message ? e.message : e);
    result = { error: message };
    if (/-1743|not authori[sz]ed|non autoris/i.test(message)) {
      result.hint = "macOS refuse le contrôle de Mail : l'utilisateur doit l'autoriser dans Réglages Système > Confidentialité et sécurité > Automatisation.";
    }
  }
  return JSON.stringify(result, null, 2);
}

const COMMANDS = {
  status() {
    const Mail = Application('Mail');
    if (!Mail.running()) {
      return { mail_running: false, note: "Mail n'est pas ouvert ; la prochaine commande le lancera." };
    }
    return { mail_running: true, automation_access: true, accounts: Mail.accounts.name().length };
  },

  accounts() {
    const Mail = Application('Mail');
    const names = Mail.accounts.name();
    const enabled = Mail.accounts.enabled();
    const addresses = Mail.accounts.emailAddresses();
    return names.map((name, i) => ({ name, enabled: enabled[i], addresses: addresses[i] }));
  },

  mailboxes(o) {
    const Mail = Application('Mail');
    const accounts = o.account ? [account(Mail, o.account)] : Mail.accounts();
    const result = accounts.map(a => ({ account: a.name(), mailboxes: boxes(a.mailboxes) }));
    if (!o.account && Mail.mailboxes.name().length) {
      result.push({ account: null, label: 'Sur mon Mac', mailboxes: boxes(Mail.mailboxes) });
    }
    return result;
  },

  // list et search lisent chaque boîte en bloc (une requête par propriété) : l'accès
  // message par message est beaucoup trop lent dans Mail sur les grosses boîtes.
  list(o) {
    const Mail = Application('Mail');
    const limit = int(o.limit, 20, 1, 200);
    const scope = targets(Mail, o);
    const all = scope.flatMap(snapshot);
    let rows = all;
    if (o['unread-only']) rows = rows.filter(r => !r.read);
    if (o.since) {
      const since = day(o.since);
      rows = rows.filter(r => r.date >= since);
    }
    rows.sort((a, b) => b.date - a.date);
    return {
      scope: scope.map(t => t.where), total: all.length, matching: rows.length,
      messages: rows.slice(0, limit).map(row),
    };
  },

  search(o) {
    if (!o.query) throw new Error('--query requis');
    const Mail = Application('Mail');
    const limit = int(o.limit, 20, 1, 200);
    const scope = targets(Mail, o);
    let rows = scope.flatMap(snapshot);
    if (o.since) {
      const since = day(o.since);
      rows = rows.filter(r => r.date >= since);
    }
    rows.sort((a, b) => b.date - a.date);
    const needle = fold(o.query);
    const hits = rows.filter(r => fold(r.subject).includes(needle) || fold(r.from).includes(needle));
    let scanned = 0;
    if (o.content) {
      // Recherche dans le texte : un accès par message, donc lente ; limitée aux plus récents.
      const scan = int(o.scan, 50, 1, 500);
      const matched = new Set(hits);
      for (const r of rows.filter(x => !matched.has(x)).slice(0, scan)) {
        scanned++;
        if (fold(r.box.messages.byId(r.id).content()).includes(needle)) hits.push(r);
      }
      hits.sort((a, b) => b.date - a.date);
    }
    return {
      scope: scope.map(t => t.where), query: o.query, matching: hits.length,
      content_scanned: scanned, messages: hits.slice(0, limit).map(row),
    };
  },

  read(o) {
    const Mail = Application('Mail');
    const { msg, where } = message(Mail, o);
    const max = int(o['max-chars'], 20000, 200, 500000);
    const content = msg.content() || '';
    let attachments = [];
    try {
      const atts = msg.mailAttachments;
      const names = atts.name();
      const sizes = atts.fileSize();
      const downloaded = atts.downloaded();
      attachments = names.map((name, i) => ({ name, size: sizes[i], downloaded: downloaded[i] }));
    } catch (e) {
      attachments = [];
    }
    return Object.assign(summary(msg, where), {
      to: addresses(msg.toRecipients),
      cc: addresses(msg.ccRecipients),
      reply_to: msg.replyTo(),
      date_sent: iso(msg.dateSent()),
      message_id: msg.messageId(),
      attachments,
      content_length: content.length,
      content_truncated: content.length > max,
      content: content.slice(0, max),
    });
  },

  mark(o) {
    const Mail = Application('Mail');
    if ((o.read && o.unread) || (o.flag && o.unflag)) throw new Error('Options contradictoires');
    const { msg, where } = message(Mail, o);
    const changes = [];
    if (o.read) { msg.readStatus = true; changes.push('lu'); }
    if (o.unread) { msg.readStatus = false; changes.push('non lu'); }
    if (o.flag) { msg.flaggedStatus = true; changes.push('drapeau'); }
    if (o.unflag) { msg.flaggedStatus = false; changes.push('sans drapeau'); }
    if (!changes.length) throw new Error('Préciser --read, --unread, --flag ou --unflag');
    return { done: true, changes, message: summary(msg, where) };
  },

  move(o) {
    const Mail = Application('Mail');
    if (!o['to-mailbox']) throw new Error('--to-mailbox requis');
    const { msg, where } = message(Mail, o);
    const dest = mailbox(Mail, o['to-account'] || (where && where.account) || o.account, o['to-mailbox']);
    const plan = {
      action: 'déplacer',
      message: summary(msg, where),
      destination: { account: dest.account, mailbox: dest.name },
    };
    return gated(o, plan, () => Mail.move(msg, { to: dest.box }));
  },

  trash(o) {
    const Mail = Application('Mail');
    const { msg, where } = message(Mail, o);
    const acc = account(Mail, (where && where.account) || o.account);
    const names = acc.mailboxes.name();
    const candidates = names.map((_, i) => i).filter(i => /trash|corbeille|deleted|supprim/i.test(names[i]));
    if (candidates.length !== 1) {
      const listed = candidates.map(i => names[i]).join(', ') || 'aucune';
      throw new Error(`Corbeille du compte ambiguë ou introuvable (${listed}) : utiliser move avec --to-mailbox explicite.`);
    }
    const plan = {
      action: 'mettre à la corbeille (réversible)',
      message: summary(msg, where),
      destination: { account: acc.name(), mailbox: names[candidates[0]] },
    };
    return gated(o, plan, () => Mail.move(msg, { to: acc.mailboxes[candidates[0]] }));
  },

  'save-attachment'(o) {
    const Mail = Application('Mail');
    if (!o.name || !o.dest) throw new Error('--name et --dest requis');
    if (!o.dest.startsWith('/') || !isDir(o.dest)) throw new Error('--dest doit être un dossier existant, en chemin absolu');
    const { msg, where } = message(Mail, o);
    const names = msg.mailAttachments.name();
    const i = names.indexOf(o.name);
    if (i < 0) throw new Error(`Pièce jointe « ${o.name} » absente. Pièces jointes : ${names.join(', ') || 'aucune'}`);
    const target = `${o.dest.replace(/\/+$/, '')}/${o.name.replace(/\//g, '-')}`;
    if (exists(target)) throw new Error(`Fichier déjà présent, rien n'a été écrasé : ${target}`);
    Mail.save(msg.mailAttachments[i], { in: Path(target) });
    if (!exists(target)) throw new Error("Mail n'a pas enregistré la pièce jointe (téléchargement incomplet ?)");
    return { done: true, saved: target, message: summary(msg, where) };
  },

  draft(o) {
    const Mail = Application('Mail');
    const c = composition(Mail, o);
    build(Mail, c, true);
    Mail.activate();
    return {
      done: true, plan: c.plan,
      note: "Fenêtre de rédaction ouverte dans Mail. Rien n'a été envoyé : l'utilisateur relit et envoie lui-même.",
    };
  },

  send(o) {
    const Mail = Application('Mail');
    const c = composition(Mail, o);
    return gated(o, c.plan, () => {
      const out = build(Mail, c, false);
      const actual = new Set([].concat(
        out.toRecipients.address(), out.ccRecipients.address(), out.bccRecipients.address(),
      ).map(a => a.toLowerCase()));
      const unexpected = [...actual].filter(a => !c.allowed.has(a));
      if (unexpected.length || !actual.size) {
        out.visible = true;
        throw new Error(`Envoi annulé : destinataires inattendus (${unexpected.join(', ') || 'aucun destinataire'}). Le message est laissé ouvert dans Mail, non envoyé.`);
      }
      out.send();
    });
  },
};

// --- Résolution des comptes, boîtes et messages ---

function account(Mail, name) {
  if (!name) throw new Error('--account requis');
  const names = Mail.accounts.name();
  const i = indexOfName(names, name);
  if (i < 0) throw new Error(`Compte introuvable : ${name}. Comptes : ${names.join(', ')}`);
  return Mail.accounts[i];
}

// Sans --account : les boîtes de réception de chaque compte (la boîte unifiée de Mail
// est trop lente), ou une boîte locale « Sur mon Mac » si --mailbox en nomme une autre.
function targets(Mail, o) {
  if (o.account) return [mailbox(Mail, o.account, o.mailbox)];
  if (o.mailbox && !isInbox(o.mailbox)) return [mailbox(Mail, null, o.mailbox)];
  return Mail.accounts.name()
    .map(name => { try { return mailbox(Mail, name, null); } catch (e) { return null; } })
    .filter(Boolean);
}

function snapshot(t) {
  const msgs = t.box.messages;
  const ids = msgs.id();
  if (!ids.length) return [];
  const dates = msgs.dateReceived();
  const senders = msgs.sender();
  const subjects = msgs.subject();
  const read = msgs.readStatus();
  const flagged = msgs.flaggedStatus();
  return ids.map((id, i) => ({
    id, date: dates[i], from: senders[i], subject: subjects[i], read: read[i], flagged: flagged[i],
    account: t.account, mailbox: t.name, box: t.box,
  }));
}

function row(r) {
  return {
    id: r.id, date: iso(r.date), from: r.from, subject: r.subject,
    read: r.read, flagged: r.flagged, account: r.account, mailbox: r.mailbox,
  };
}

function isInbox(name) {
  return INBOX_NAMES.includes(name.toLowerCase());
}

function fold(s) {
  return (s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
}

function mailbox(Mail, accountName, mailboxName) {
  const wantsInbox = !mailboxName || isInbox(mailboxName);
  if (!accountName) {
    if (wantsInbox) throw new Error('--account requis pour désigner une boîte de réception précise');
    const names = Mail.mailboxes.name();
    const i = indexOfName(names, mailboxName);
    if (i < 0) throw new Error(`Boîte « ${mailboxName} » introuvable hors compte : préciser --account.`);
    return { box: Mail.mailboxes[i], account: null, name: names[i], where: { account: null, mailbox: names[i] } };
  }
  const acc = account(Mail, accountName);
  const names = acc.mailboxes.name();
  const i = wantsInbox ? names.findIndex(isInbox) : indexOfName(names, mailboxName);
  if (i < 0) throw new Error(`Boîte « ${mailboxName || 'INBOX'} » introuvable dans ${acc.name()}. Boîtes : ${names.join(', ')}`);
  return { box: acc.mailboxes[i], account: acc.name(), name: names[i], where: { account: acc.name(), mailbox: names[i] } };
}

function message(Mail, o) {
  if (!o.id) throw new Error('--id requis, avec --account et --mailbox tels que renvoyés par list ou search');
  const t = mailbox(Mail, o.account, o.mailbox);
  const msg = t.box.messages.byId(Number(o.id));
  if (!msg.exists()) throw new Error(`Message ${o.id} introuvable dans ${t.name}`);
  return { msg, where: t.where };
}

function indexOfName(names, wanted) {
  const i = names.indexOf(wanted);
  if (i >= 0) return i;
  const w = wanted.toLowerCase();
  return names.findIndex(n => n.toLowerCase() === w);
}

function boxes(spec) {
  const names = spec.name();
  const unread = spec.unreadCount();
  return names.map((name, i) => ({ name, unread: unread[i] }));
}

function summary(msg, where) {
  return Object.assign({
    id: msg.id(),
    date: iso(msg.dateReceived()),
    from: msg.sender(),
    subject: msg.subject(),
    read: msg.readStatus(),
    flagged: msg.flaggedStatus(),
  }, where);
}

function addresses(spec) {
  const addrs = spec.address();
  const names = spec.name();
  return addrs.map((a, i) => (names[i] ? `${names[i]} <${a}>` : a));
}

// --- Rédaction ---

function composition(Mail, o) {
  const mode = o.mode || 'new';
  if (!['new', 'reply', 'reply-all', 'forward'].includes(mode)) throw new Error(`--mode inconnu : ${mode}`);
  const body = o['body-file'] ? readText(o['body-file']) : (o.body || '');
  const attach = (o.attach || []).map(p => {
    if (!p.startsWith('/') || !exists(p)) throw new Error(`Pièce jointe introuvable (chemin absolu requis) : ${p}`);
    return p;
  });
  const plan = {
    mode, from: o.from || '(adresse par défaut de Mail)',
    to: o.to || [], cc: o.cc || [], bcc: o.bcc || [],
    subject: o.subject || null, body, attachments: attach,
  };
  const allowed = new Set([].concat(plan.to, plan.cc, plan.bcc).map(a => a.toLowerCase()));
  let orig = null;
  if (mode === 'new' || mode === 'forward') {
    if (!plan.to.length) throw new Error('--to requis');
  }
  if (mode !== 'new') {
    const m = message(Mail, o);
    orig = m.msg;
    plan.original = summary(m.msg, m.where);
    if (mode !== 'forward') {
      const own = new Set([].concat(...Mail.accounts.emailAddresses()).map(a => a.toLowerCase()));
      const base = [bare(orig.replyTo() || orig.sender())];
      if (mode === 'reply-all') {
        base.push(...orig.toRecipients.address(), ...orig.ccRecipients.address());
      }
      const expected = [...new Set(base.map(a => a.toLowerCase()))].filter(a => a && !own.has(a));
      expected.forEach(a => allowed.add(a));
      plan.reply_recipients = expected;
    }
  }
  return { plan, orig, body, attach, allowed, from: o.from };
}

function build(Mail, c, visible) {
  const p = c.plan;
  let out;
  if (p.mode === 'new') {
    out = Mail.OutgoingMessage({ subject: p.subject || '', content: c.body, visible });
    Mail.outgoingMessages.push(out);
  } else {
    out = p.mode === 'forward'
      ? Mail.forward(c.orig, { openingWindow: visible })
      : Mail.reply(c.orig, { openingWindow: visible, replyToAll: p.mode === 'reply-all' });
    if (c.body) out.content = `${c.body}\n\n${out.content() || ''}`;
    if (p.subject) out.subject = p.subject;
  }
  if (c.from) out.sender = c.from;
  p.to.forEach(a => out.toRecipients.push(Mail.ToRecipient({ address: a })));
  p.cc.forEach(a => out.ccRecipients.push(Mail.CcRecipient({ address: a })));
  p.bcc.forEach(a => out.bccRecipients.push(Mail.BccRecipient({ address: a })));
  c.attach.forEach(path => out.attachments.push(Mail.Attachment({ fileName: Path(path) })));
  return out;
}

function gated(o, plan, act) {
  if (!o.confirm) {
    return {
      preview: true, plan,
      note: "Aperçu seulement : rien n'a été modifié ni envoyé. Relancer exactement la même commande avec --confirm après l'accord explicite de l'utilisateur.",
    };
  }
  act();
  return { done: true, plan };
}

// --- Utilitaires ---

function parseArgs(args) {
  const o = {};
  for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (!a.startsWith('--')) throw new Error(`Argument inattendu : ${a}`);
    const key = a.slice(2);
    if (FLAGS.has(key)) { o[key] = true; continue; }
    const value = args[++i];
    if (value === undefined) throw new Error(`Valeur manquante pour --${key}`);
    if (MULTI.has(key)) (o[key] = o[key] || []).push(value);
    else o[key] = value;
  }
  return o;
}

function int(v, def, min, max) {
  if (v === undefined) return def;
  const n = parseInt(v, 10);
  if (!(n >= min && n <= max)) throw new Error(`Valeur hors limites (${min}–${max}) : ${v}`);
  return n;
}

function day(s) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
  if (!m) throw new Error(`Date attendue au format AAAA-MM-JJ : ${s}`);
  return new Date(+m[1], +m[2] - 1, +m[3]);
}

function iso(d) {
  if (!d) return null;
  const p = n => String(n).padStart(2, '0');
  const off = -d.getTimezoneOffset();
  const sign = off >= 0 ? '+' : '-';
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
    + `${sign}${p(Math.floor(Math.abs(off) / 60))}:${p(Math.abs(off) % 60)}`;
}

function bare(address) {
  const m = /<([^>]+)>/.exec(address || '');
  return (m ? m[1] : address || '').trim();
}

function exists(path) {
  return $.NSFileManager.defaultManager.fileExistsAtPath(path);
}

function isDir(path) {
  const flag = Ref();
  return $.NSFileManager.defaultManager.fileExistsAtPathIsDirectory(path, flag) && flag[0];
}

function readText(path) {
  if (!path.startsWith('/')) throw new Error(`--body-file doit être un chemin absolu : ${path}`);
  const s = $.NSString.stringWithContentsOfFileEncodingError(path, $.NSUTF8StringEncoding, null);
  if (!s || s.isNil()) throw new Error(`Lecture impossible : ${path}`);
  return ObjC.unwrap(s);
}
