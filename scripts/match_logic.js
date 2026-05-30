/**
 * Reference matching logic (defaults mirror config/match-profile.example.yaml).
 * n8n workflows embed equivalent logic inline — update both when changing rules.
 */

const DEFAULT_PROFILE = {
  naics_codes: ['541511', '541512', '541519', '518210', '511210'],
  psc_prefixes: ['D3', '7E'],
  include_keywords: [
    'software', 'application', 'cloud', 'devsecops', 'cybersecurity',
    'api', 'modernization', 'saas', 'database', 'agile',
  ],
  exclude_keywords: [
    'construction', 'janitorial', 'landscaping', 'hardware only',
    'furniture', 'vehicles',
  ],
  exclude_set_asides: ['8(a)', 'HUBZone', 'SDVOSB', 'WOSB', 'EDWOSB'],
};

function normalizeKey(key) {
  return String(key || '').toLowerCase().replace(/[^a-z0-9]/g, '');
}

function pick(row, ...keys) {
  const map = {};
  for (const [k, v] of Object.entries(row)) {
    map[normalizeKey(k)] = v;
  }
  for (const key of keys) {
    const val = map[normalizeKey(key)];
    if (val !== undefined && val !== null && String(val).trim() !== '') {
      return String(val).trim();
    }
  }
  return null;
}

function parseDate(val) {
  if (!val) return null;
  const d = new Date(val);
  return Number.isNaN(d.getTime()) ? null : d.toISOString().slice(0, 10);
}

function parseTimestamp(val) {
  if (!val) return null;
  const d = new Date(val);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}

function computeRuleScore(opp, profile = DEFAULT_PROFILE) {
  let score = 0;
  const reasons = [];
  const title = (opp.title || '').toLowerCase();
  const naics = opp.naics || '';
  const psc = opp.psc || '';
  const setAside = (opp.set_aside || '').toLowerCase();

  if (profile.naics_codes.includes(naics)) {
    score += 40;
    reasons.push('naics_match');
  }
  if (profile.psc_prefixes.some((p) => psc.startsWith(p))) {
    score += 20;
    reasons.push('psc_match');
  }
  for (const kw of profile.include_keywords) {
    if (title.includes(kw.toLowerCase())) {
      score += 10;
      reasons.push(`keyword:${kw}`);
    }
  }
  score = Math.min(score, 90);
  for (const kw of profile.exclude_keywords) {
    if (title.includes(kw.toLowerCase())) {
      score = Math.max(0, score - 50);
      reasons.push(`exclude:${kw}`);
    }
  }
  for (const ex of profile.exclude_set_asides) {
    if (setAside.includes(ex.toLowerCase())) {
      score = 0;
      reasons.push('set_aside_excluded');
      break;
    }
  }
  return { rule_score: Math.min(100, score), match_reasons: reasons };
}

function passesHardFilter(opp, profile = DEFAULT_PROFILE) {
  const naics = opp.naics || '';
  const psc = opp.psc || '';
  const title = (opp.title || '').toLowerCase();

  if (profile.naics_codes.includes(naics)) return true;
  if (profile.psc_prefixes.some((p) => psc.startsWith(p))) return true;
  if (profile.include_keywords.some((kw) => title.includes(kw.toLowerCase()))) return true;
  return false;
}

function mapSamCsvRow(row, source = 'federal:sam') {
  const noticeId = pick(row, 'NoticeId', 'Notice ID', 'noticeid', 'notice_id');
  if (!noticeId) return null;

  const opp = {
    notice_id: noticeId,
    source,
    solicitation_number: pick(row, 'Sol#', 'SolicitationNumber', 'Solicitation Number', 'solnumber'),
    title: pick(row, 'Title', 'title'),
    posted_date: parseDate(pick(row, 'PostedDate', 'Posted Date', 'posteddate')),
    response_deadline: parseTimestamp(pick(row, 'ResponseDeadLine', 'Response Deadline', 'responsedeadline')),
    naics: pick(row, 'NaicsCode', 'NAICS Code', 'naics', 'naicscode'),
    psc: pick(row, 'ClassificationCode', 'PSC', 'psc', 'classificationcode'),
    set_aside: pick(row, 'SetASide', 'Set Aside', 'setaside'),
    set_aside_code: pick(row, 'SetAsideCode', 'Set Aside Code'),
    procurement_type: pick(row, 'Type', 'ptype', 'Notice Type'),
    agency: pick(row, 'Department/Ind.Agency', 'Department', 'Agency', 'agency'),
    office: pick(row, 'Office', 'Sub-Tier', 'office'),
    place_of_performance: pick(row, 'PopCity', 'Place of Performance', 'placeofperformance'),
    state_code: pick(row, 'PopState', 'State', 'state'),
    ui_link: pick(row, 'Link', 'uiLink', 'UiLink'),
    description_url: pick(row, 'Description', 'description'),
    active: true,
    raw_data: row,
  };
  return opp;
}

function mapSamApiRecord(rec, source = 'federal:sam') {
  const noticeId = rec.noticeId || rec.noticeid;
  if (!noticeId) return null;

  const pop = rec.placeOfPerformance || {};
  const contacts = Array.isArray(rec.pointOfContact) ? rec.pointOfContact : [];
  const links = Array.isArray(rec.resourceLinks) ? rec.resourceLinks : [];

  const opp = {
    notice_id: noticeId,
    source,
    solicitation_number: rec.solicitationNumber || null,
    title: rec.title || null,
    posted_date: parseDate(rec.postedDate),
    response_deadline: parseTimestamp(rec.responseDeadLine || rec.responseDeadline),
    naics: rec.naicsCode || rec.naics || null,
    psc: rec.classificationCode || null,
    set_aside: rec.setAside || null,
    set_aside_code: rec.setAsideCode || null,
    procurement_type: rec.type || rec.ptype || null,
    agency: rec.fullParentPathName || rec.department || null,
    office: rec.officeAddress || null,
    place_of_performance: [pop.city, pop.state, pop.zip].filter(Boolean).join(', ') || null,
    state_code: pop.state || null,
    ui_link: rec.uiLink || null,
    description_url: rec.description || null,
    active: true,
    raw_data: rec,
    contacts: contacts.map((c) => ({
      contact_type: c.type || 'primary',
      name: [c.fullName, c.firstName, c.lastName].filter(Boolean).join(' ') || null,
      email: c.email || null,
      phone: c.fax || c.phone || null,
    })),
    attachments: links.map((url) => ({ url, description: 'resource_link' })),
  };
  return opp;
}

module.exports = {
  DEFAULT_PROFILE,
  pick,
  mapSamCsvRow,
  mapSamApiRecord,
  passesHardFilter,
  computeRuleScore,
};
