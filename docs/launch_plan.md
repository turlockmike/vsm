# VSM Launch Strategy

## Current State
- **GitHub**: 0 stars, 0 watchers, 0 forks
- **Competition**: 12+ autonomous AI systems in active development (OpenClaw clones, multi-agent frameworks)
- **Product Status**: Production-ready (demo, dashboard, persistent memory, self-healing)
- **Unique Position**: Only autonomous AI system built entirely on Claude Code CLI

## Goal
Become the world's most popular AI computer system built on Claude Code.

## Three-Phase Launch

### Phase 1: Show HN (Week 1)
**Platform**: Hacker News (https://news.ycombinator.com)

**Timeline**:
- Day 1 (Tuesday or Wednesday, 8am PST): Post Show HN
- Monitor for 24 hours, respond to every comment within 2 hours
- Iterate based on feedback

**Target Metrics**:
- Front page for 4+ hours
- 50+ upvotes
- 20+ comments
- 5+ GitHub stars

**Content**: See `show_hn_draft.md`

**Post-Launch Actions**:
1. Respond to technical questions immediately
2. Accept feature requests as GitHub issues
3. Fix critical bugs within 24 hours
4. Document common setup issues
5. Add "As seen on HN" badge to README if front page

**Risk Mitigation**:
- Have demo GIF working perfectly before posting
- Test install.sh on fresh Ubuntu 22.04 VM
- Pre-write answers to likely questions (setup issues, Claude API costs, security)
- Be online and responsive for first 6 hours

---

### Phase 2: Reddit (Week 2)
**Platforms**: /r/LocalLLaMA, /r/SelfHosted, /r/ClaudeAI

**Timeline**:
- Day 8 (Monday): Post to /r/LocalLLaMA (peak activity 9am-12pm PST)
- Day 9 (Tuesday): Post to /r/SelfHosted (peak activity 10am-2pm PST)
- Day 10 (Wednesday): Post to /r/ClaudeAI (peak activity 8am-11am PST)

**Target Metrics**:
- 100+ upvotes per subreddit
- 30+ comments per post
- 10+ GitHub stars from Reddit traffic

**Content**: See `reddit_templates.md`

**Post-Launch Actions**:
1. Cross-link to HN discussion for social proof
2. Engage with critiques (don't defend, acknowledge and iterate)
3. Post setup guides if installation issues emerge
4. Create comparison table if competing systems are mentioned

**Risk Mitigation**:
- Read community rules carefully (some subs ban self-promotion)
- Frame posts as "built this to solve X problem" not "check out my product"
- Have 100+ comment karma on Reddit account before posting
- Disclose affiliation clearly ("I built this")

---

### Phase 3: Product Hunt (Week 3)
**Platform**: Product Hunt (https://producthunt.com)

**Timeline**:
- Day 16 (Tuesday, 12:01am PST): Launch on Product Hunt
- Monitor for 48 hours, respond to all comments
- Leverage any HN/Reddit momentum for social proof

**Target Metrics**:
- 200+ upvotes
- Top 5 product of the day
- 50+ comments
- 25+ GitHub stars from PH traffic

**Content**: See `ph_checklist.md`

**Post-Launch Actions**:
1. Thank top commenters personally
2. Address feature requests in comments
3. Update README with "Product of the Day" badge if applicable
4. Email community update to early users

**Risk Mitigation**:
- Use established PH hunter account or build credibility first
- Have 5-10 supporters ready to upvote/comment in first hour
- Polish gallery images (screenshots + demo GIF)
- Pre-schedule social media posts (Twitter, LinkedIn) to launch same day

---

## Content Strategy

### Key Messages (Consistent Across Platforms)
1. **What it is**: Autonomous AI computer that runs on your machine
2. **Why it exists**: AI should work FOR you, not require constant supervision
3. **How it's different**: Built entirely on Claude Code, self-healing, email interface
4. **Proof**: Working demo GIF, open source code, active development

### Differentiation from Competitors
- OpenClaw: Requires Electron, JavaScript-heavy, no Claude Code integration
- AutoGPT/AgentGPT: Cloud-based, no self-hosting option
- LangChain agents: Library/framework, not a complete system
- VSM: Self-contained, Claude Code-native, runs on your hardware

### Tone Guidelines
- **Hacker News**: Technical, humble, factual. Focus on architecture and implementation.
- **Reddit**: Authentic, problem-focused. "I built this because X was frustrating."
- **Product Hunt**: Value-focused, visual. "This is what it does for you."

---

## Success Criteria

### Week 1 (Post-HN)
- [ ] 10+ GitHub stars
- [ ] 3+ external contributors (issues/PRs)
- [ ] 5+ successful installations reported

### Week 2 (Post-Reddit)
- [ ] 25+ GitHub stars
- [ ] 10+ external contributors
- [ ] 15+ successful installations

### Week 3 (Post-PH)
- [ ] 50+ GitHub stars
- [ ] 20+ external contributors
- [ ] 30+ successful installations
- [ ] First external use case documented

### Month 1
- [ ] 100+ GitHub stars
- [ ] Active community (Discord/Slack?)
- [ ] 5+ external contributions merged
- [ ] Featured in AI newsletter or blog

---

## Failure Modes & Recovery

### Scenario: HN post gets flagged/removed
- **Recovery**: Repost 48 hours later with clearer title, or post in "Who's Hiring" thread as YC founder looking for feedback

### Scenario: Reddit community rejects as self-promotion
- **Recovery**: Delete post, wait 1 week, reframe as "Show & Tell" with focus on technical learnings

### Scenario: Product Hunt launch flops (<50 upvotes)
- **Recovery**: Don't force it. Focus on organic growth via HN/Reddit, return to PH in 3 months with v2

### Scenario: Installation issues dominate discussion
- **Recovery**:
  1. Acknowledge publicly
  2. Ship fix within 24 hours
  3. Update install.sh
  4. Post follow-up "We fixed it" thread

### Scenario: No traction anywhere
- **Recovery**:
  1. Direct outreach to AI influencers (Twitter, YouTube)
  2. Write technical blog post about architecture
  3. Submit to AI aggregators (ArtificialCorner, FutureTools)
  4. Pivot messaging based on feedback

---

## Content Calendar

| Day | Action | Platform | Owner Effort |
|-----|--------|----------|--------------|
| 0 | Final polish: test install, verify demo, check README | GitHub | 2 hours |
| 1 | Post Show HN | HN | 30 min + monitoring |
| 1-2 | Respond to HN comments | HN | 4 hours |
| 3-7 | Iterate on feedback, ship improvements | GitHub | Daily cycles |
| 8 | Post to /r/LocalLLaMA | Reddit | 30 min + monitoring |
| 9 | Post to /r/SelfHosted | Reddit | 30 min + monitoring |
| 10 | Post to /r/ClaudeAI | Reddit | 30 min + monitoring |
| 8-14 | Respond to Reddit discussions | Reddit | 2 hours/day |
| 15 | Finalize PH assets (screenshots, tagline) | Product Hunt | 3 hours |
| 16 | Launch on Product Hunt | Product Hunt | 30 min + monitoring |
| 16-17 | Respond to PH comments | Product Hunt | 4 hours |
| 18-30 | Community engagement, feature requests, bug fixes | All platforms | Ongoing |

---

## Pre-Launch Checklist

Before posting Show HN:

- [ ] Install.sh tested on Ubuntu 22.04, Debian 12, macOS 14
- [ ] Demo GIF working (vsm-demo.gif loads in README)
- [ ] README is polished (no typos, clear value prop)
- [ ] GitHub repo has topics/tags (autonomous-ai, claude-code, viable-system-model)
- [ ] License file present (MIT)
- [ ] Contributing.md present (even if minimal)
- [ ] GitHub Issues enabled with templates
- [ ] Email alerts working (test full cycle)
- [ ] Dashboard accessible on localhost:80
- [ ] No embarrassing debug logs or TODOs in main branch
- [ ] All tests passing (if tests exist)
- [ ] .env.example present with clear instructions
- [ ] Security audit complete (no API keys in repo)

---

## Monitoring & Analytics

Track these metrics daily during launch period:

- GitHub stars (use API: `gh api /repos/turlockmike/vsm | jq .stargazers_count`)
- GitHub traffic (Insights > Traffic)
- Unique clones (Insights > Traffic > Clones)
- Referral sources (where traffic comes from)
- Issue velocity (issues opened vs closed)
- Community sentiment (positive/neutral/negative comments)

Tools:
- GitHub Insights (built-in analytics)
- Google Analytics (optional, add to dashboard if public-facing)
- Star History (https://star-history.com) for visualization

---

## Post-Launch Communication

After each platform launch, VSM should:

1. Email owner with metrics (stars, comments, issues)
2. Log key feedback themes to `state/memory/feedback.md`
3. Queue high-priority feature requests as tasks
4. Update `state/intelligence/` with competitor activity

Owner should:

1. Respond personally to thoughtful comments
2. Acknowledge critics with humility
3. Share launch updates on personal Twitter/LinkedIn
4. Document learnings in GitHub Discussions

---

## Long-Term Growth Strategy

### Month 2-3: Ecosystem Building
- Claude Code extension/plugin examples
- Community agent library (share specialized agents)
- Integration guides (Zapier, IFTTT, Home Assistant)
- Video tutorials (YouTube)

### Month 4-6: Authority Building
- Technical blog posts (architecture deep-dives)
- Conference talks (local meetups first)
- Podcast appearances (AI/dev podcasts)
- Case studies from users

### Month 7-12: Platform Effects
- VSM marketplace (pre-built agent configs)
- VSM hosting service (optional cloud option)
- Enterprise features (team collaboration)
- Training/certification program

---

## Owner Action Items

1. Review all draft content (show_hn_draft.md, reddit_templates.md, ph_checklist.md)
2. Set launch date for Show HN (recommend next Tuesday or Wednesday)
3. Test install.sh on clean VM before launch
4. Create Product Hunt account if needed (or find hunter)
5. Decide on Discord/Slack for community (post-launch)
6. Prepare personal social accounts for cross-promotion
7. Block calendar for monitoring during launch days

---

**Next Steps**: Review drafts, pick launch date, execute Phase 1.
