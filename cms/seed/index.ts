/**
 * Muraho Rwanda — Seed Data
 * Run: npm run seed (or ts-node --esm seed/index.ts)
 *
 * Creates sample content for first demo:
 *   - 1 admin user
 *   - 6 real Rwandan museums with GPS coordinates
 *   - 10 real locations (memorials, cultural sites)
 *   - 3 heritage routes with stops
 *   - 5 sample stories
 *   - AI config (tone profiles, mode configs, safety settings)
 *   - 1 tour agency with sample pricing
 */
import payload from "payload";
import { importConfig } from "payload/node";

const PAYLOAD_CONFIG_PATH = process.env.PAYLOAD_CONFIG_PATH || "./payload.config.ts";

async function seed() {
  const config = await importConfig(PAYLOAD_CONFIG_PATH);
  await payload.init({ config });

  console.log("🌱 Seeding Muraho Rwanda...\n");

  // ── 1. Admin User ──────────────────────────────────────
  const admin = await payload.create({
    collection: "users",
    data: {
      email: "admin@muraho.rw",
      password: "MurahoAdmin2026!",
      name: "Admin",
      role: "admin",
    },
  });
  console.log("✅ Admin user created: admin@muraho.rw");

  // ── 2. Museums (real GPS coordinates) ──────────────────
  const museums = [
    {
      name: "Kigali Genocide Memorial",
      slug: "kigali-genocide-memorial",
      description: "The Kigali Genocide Memorial is the final resting place for more than 250,000 victims of the Genocide against the Tutsi. It serves as a place of remembrance, education, and peace.",
      latitude: -1.9403, longitude: 29.8739,
      city: "Kigali", province: "Kigali",
      isActive: true, isFeatured: true,
      operatingHours: { weekday: "8:00 - 17:00", weekend: "8:00 - 17:00" },
      contactInfo: { phone: "+250 788 000 000", email: "info@kgm.rw" },
    },
    {
      name: "Campaign Against Genocide Museum",
      slug: "campaign-against-genocide-museum",
      description: "Located in the former Rwanda Parliament building, this museum tells the story of the international community's failure to prevent the 1994 Genocide against the Tutsi.",
      latitude: -1.9533, longitude: 29.8582,
      city: "Kigali", province: "Kigali",
      isActive: true, isFeatured: true,
    },
    {
      name: "Ethnographic Museum (National Museum of Rwanda)",
      slug: "ethnographic-museum",
      description: "Rwanda's oldest museum showcasing traditional Rwandan culture, crafts, and history. Houses extensive collections of artifacts and ethnographic objects.",
      latitude: -2.3461, longitude: 29.3489,
      city: "Huye", province: "Southern",
      isActive: true, isFeatured: false,
    },
    {
      name: "King's Palace Museum (Rukari)",
      slug: "kings-palace-museum",
      description: "A reconstructed traditional royal residence showcasing the lifestyle and culture of the Rwandan monarchy. Features traditional architecture and royal artifacts.",
      latitude: -2.3244, longitude: 29.7474,
      city: "Nyanza", province: "Southern",
      isActive: true, isFeatured: false,
    },
    {
      name: "Kandt House Museum of Natural History",
      slug: "kandt-house-museum",
      description: "Built in 1907 as the residence of Richard Kandt, the first German colonial governor. Now houses natural history exhibits and tells the story of Kigali's founding.",
      latitude: -1.9276, longitude: 29.8519,
      city: "Kigali", province: "Kigali",
      isActive: true, isFeatured: false,
    },
    {
      name: "Rwanda Art Museum (IziReka Hub)",
      slug: "rwanda-art-museum",
      description: "Rwanda's premier contemporary art space showcasing both traditional and modern Rwandan art, sculpture, and mixed-media installations.",
      latitude: -1.9460, longitude: 29.8740,
      city: "Kigali", province: "Kigali",
      isActive: true, isFeatured: false,
    },
  ];

  const museumIds: Record<string, string> = {};
  for (const m of museums) {
    const created = await payload.create({ collection: "museums", data: m as any });
    museumIds[m.slug] = created.id;
  }
  console.log(`✅ ${museums.length} museums created`);

  // ── 3. Locations (memorials + cultural sites) ──────────
  const locations = [
    { name: "Nyamata Genocide Memorial", slug: "nyamata-memorial", locationType: "memorial",
      latitude: -2.1413, longitude: 30.0906, description: "Located in a former church where thousands sought refuge. Now a memorial preserving the memory of the 45,000 people killed at this site.", isActive: true },
    { name: "Murambi Genocide Memorial", slug: "murambi-memorial", locationType: "memorial",
      latitude: -2.2853, longitude: 29.6047, description: "Formerly a technical school, this memorial preserves the remains of over 40,000 victims in a stark reminder of the 1994 genocide.", isActive: true },
    { name: "Ntarama Genocide Memorial", slug: "ntarama-memorial", locationType: "memorial",
      latitude: -2.1167, longitude: 30.0833, description: "A church memorial site where approximately 5,000 people were killed. The building has been preserved as a memorial.", isActive: true },
    { name: "Bisesero Genocide Memorial", slug: "bisesero-memorial", locationType: "memorial",
      latitude: -2.2333, longitude: 29.1667, description: "Located on a mountainside in the west, honoring the resistance fighters who held out against attackers for weeks.", isActive: true },
    { name: "Inema Arts Center", slug: "inema-arts-center", locationType: "cultural_site",
      latitude: -1.9350, longitude: 29.8800, description: "Founded by Emmanuel and Innocent Nkuranga, this arts center has become a hub for contemporary Rwandan art and creative expression.", isActive: true },
    { name: "Nyamirambo Women's Center", slug: "nyamirambo-womens-center", locationType: "cultural_site",
      latitude: -1.9636, longitude: 29.8500, description: "A community center empowering women through skills training, cultural tourism, and Nyamirambo walking tours.", isActive: true },
    { name: "Kimironko Market", slug: "kimironko-market", locationType: "cultural_site",
      latitude: -1.9350, longitude: 30.1000, description: "Kigali's largest and most vibrant market, offering crafts, textiles, produce, and an authentic local experience.", isActive: true },
    { name: "Volcanoes National Park", slug: "volcanoes-national-park", locationType: "natural_site",
      latitude: -1.4833, longitude: 29.5333, description: "Home to the endangered mountain gorilla. Part of the Virunga volcanic mountain range along Rwanda's northern border.", isActive: true },
    { name: "Lake Kivu", slug: "lake-kivu", locationType: "natural_site",
      latitude: -2.0667, longitude: 29.2500, description: "One of Africa's Great Lakes, bordered by mountains and dotted with islands. A center for recreation and culture.", isActive: true },
    { name: "Nyungwe Forest National Park", slug: "nyungwe-forest", locationType: "natural_site",
      latitude: -2.4667, longitude: 29.2500, description: "One of the oldest rainforests in Africa, home to chimpanzees, colobus monkeys, and over 300 bird species.", isActive: true },
  ];

  for (const loc of locations) {
    await payload.create({ collection: "locations", data: loc as any });
  }
  console.log(`✅ ${locations.length} locations created`);

  // ── 4. Routes with Stops ───────────────────────────────
  const routes = [
    {
      title: "Kigali Memorial Heritage Walk",
      slug: "kigali-memorial-heritage-walk",
      description: "A profound journey through Kigali's memorial sites and places of remembrance. This walk connects key sites of memory, resilience, and hope in the capital city.",
      difficulty: "easy",
      status: "published",
      durationMinutes: 180,
      distanceKm: 8.5,
      startLatitude: -1.9403, startLongitude: 29.8739,
      routePath: { type: "LineString", coordinates: [
        [29.8739, -1.9403], [29.8582, -1.9533], [29.8519, -1.9276], [29.8740, -1.9460],
      ]},
      stops: [
        { title: "Kigali Genocide Memorial", latitude: -1.9403, longitude: 29.8739, stopOrder: 1, estimatedTimeMinutes: 90, markerIcon: "memorial", markerColor: "#4B5573" },
        { title: "Campaign Against Genocide Museum", latitude: -1.9533, longitude: 29.8582, stopOrder: 2, estimatedTimeMinutes: 45, markerIcon: "museum", markerColor: "#7C3AED" },
        { title: "Kandt House Museum", latitude: -1.9276, longitude: 29.8519, stopOrder: 3, estimatedTimeMinutes: 30, markerIcon: "museum", markerColor: "#7C3AED" },
        { title: "Rwanda Art Museum", latitude: -1.9460, longitude: 29.8740, stopOrder: 4, estimatedTimeMinutes: 30, markerIcon: "cultural", markerColor: "#C46A4A" },
      ],
    },
    {
      title: "Southern Cultural Circuit",
      slug: "southern-cultural-circuit",
      description: "Explore Rwanda's southern province, visiting the royal palace, ethnographic museum, and scenic landscapes between Nyanza and Huye.",
      difficulty: "moderate",
      status: "published",
      durationMinutes: 360,
      distanceKm: 45,
      startLatitude: -2.3244, startLongitude: 29.7474,
      routePath: { type: "LineString", coordinates: [
        [29.7474, -2.3244], [29.3489, -2.3461],
      ]},
      stops: [
        { title: "King's Palace Museum (Nyanza)", latitude: -2.3244, longitude: 29.7474, stopOrder: 1, estimatedTimeMinutes: 60, markerIcon: "palace", markerColor: "#D4A843" },
        { title: "Ethnographic Museum (Huye)", latitude: -2.3461, longitude: 29.3489, stopOrder: 2, estimatedTimeMinutes: 90, markerIcon: "museum", markerColor: "#7C3AED" },
      ],
    },
    {
      title: "Nyamirambo Cultural Walk",
      slug: "nyamirambo-cultural-walk",
      description: "Discover the vibrant neighborhood of Nyamirambo with local guides. Visit the women's center, taste local food, explore markets, and learn about daily life in Kigali's most diverse district.",
      difficulty: "easy",
      status: "published",
      durationMinutes: 120,
      distanceKm: 3.5,
      startLatitude: -1.9636, startLongitude: 29.8500,
      routePath: { type: "LineString", coordinates: [
        [29.8500, -1.9636], [29.8520, -1.9580], [29.8550, -1.9536],
      ]},
      stops: [
        { title: "Nyamirambo Women's Center", latitude: -1.9636, longitude: 29.8500, stopOrder: 1, estimatedTimeMinutes: 30, markerIcon: "community", markerColor: "#059669" },
        { title: "Local Tailors Quarter", latitude: -1.9580, longitude: 29.8520, stopOrder: 2, estimatedTimeMinutes: 20, markerIcon: "market", markerColor: "#F97316" },
        { title: "Nyamirambo Mosque Area", latitude: -1.9536, longitude: 29.8550, stopOrder: 3, estimatedTimeMinutes: 15, markerIcon: "cultural", markerColor: "#C46A4A" },
      ],
    },
  ];

  for (const route of routes) {
    const { stops, ...routeData } = route;
    const created = await payload.create({ collection: "routes", data: routeData as any });
    for (const stop of stops) {
      await payload.create({ collection: "route-stops", data: { ...stop, route: created.id } as any });
    }
  }
  console.log(`✅ ${routes.length} routes with ${routes.reduce((n, r) => n + r.stops.length, 0)} stops created`);

  // ── 5. Stories ─────────────────────────────────────────
  const stories = [
    {
      title: "The Thousand Hills: Rwanda's Living Landscape",
      slug: "thousand-hills-landscape",
      summary: "Rwanda is called the 'Land of a Thousand Hills' — but these hills carry stories that span centuries. From ancient kingdoms to modern transformation, the landscape itself is a witness to history.",
      status: "published", isFeatured: true,
      hasSensitiveContent: false, sensitivityLevel: "standard",
    },
    {
      title: "Rebuilding Together: Stories of Reconciliation",
      slug: "rebuilding-together-reconciliation",
      summary: "In the decades following the Genocide against the Tutsi, Rwandans have embarked on one of the most remarkable reconciliation processes in human history.",
      status: "published", isFeatured: true,
      hasSensitiveContent: true, sensitivityLevel: "sensitive",
    },
    {
      title: "Imigongo: The Art of Cow Dung Painting",
      slug: "imigongo-cow-dung-painting",
      summary: "Imigongo is a unique Rwandan art form dating back centuries, created from cow dung molded into geometric patterns and painted in bold black, white, and red.",
      status: "published", isFeatured: false,
      hasSensitiveContent: false, sensitivityLevel: "standard",
    },
    {
      title: "Gorillas in the Mist: Conservation in Rwanda",
      slug: "gorillas-conservation-rwanda",
      summary: "Rwanda's mountain gorillas were once on the brink of extinction. Today, thanks to decades of conservation work, their population is growing — a story of hope and dedication.",
      status: "published", isFeatured: false,
      hasSensitiveContent: false, sensitivityLevel: "standard",
    },
    {
      title: "Umuganda: Rwanda's Community Work Tradition",
      slug: "umuganda-community-work",
      summary: "On the last Saturday of every month, Rwandans come together for Umuganda — a national day of community service rooted in traditional values of collective responsibility.",
      status: "published", isFeatured: false,
      hasSensitiveContent: false, sensitivityLevel: "standard",
    },
  ];

  for (const story of stories) {
    await payload.create({ collection: "stories", data: story as any });
  }
  console.log(`✅ ${stories.length} stories created`);

  // ── 6. AI Configuration ────────────────────────────────
  const toneProfiles = [
    { name: "Standard Guide", mode: "standard", isActive: true,
      systemPrompt: "You are Ask Rwanda, a knowledgeable and respectful AI assistant for the Muraho Rwanda app. Your purpose is to help users understand Rwanda's history, heritage, culture, memorials, and travel experiences. Be factual, educational, and culturally sensitive." },
    { name: "Personal Voices", mode: "personal_voices", isActive: true,
      systemPrompt: "You are Ask Rwanda in Personal Voices mode. Prioritize personal testimonies and survivor stories. Use a warm, empathetic tone. Always center the dignity of the people whose stories you share." },
    { name: "Kid Friendly", mode: "kid_friendly", isActive: true,
      systemPrompt: "You are Ask Rwanda for young explorers! Use simple, age-appropriate language. Focus on nature, culture, and positive stories. Be encouraging and fun while remaining educational." },
  ];

  for (const tp of toneProfiles) {
    await payload.create({ collection: "ai-tone-profiles", data: tp as any });
  }

  const modeConfigs = [
    { mode: "standard", maxAnswerTokens: 512, temperature: 0.3, includeStories: true, includePanels: true, includeTestimonies: true, includeRoutes: true, preferTestimonies: false, blockSensitiveContent: false, useSimplifiedLanguage: false },
    { mode: "personal_voices", maxAnswerTokens: 768, temperature: 0.4, includeStories: true, includePanels: true, includeTestimonies: true, includeRoutes: false, preferTestimonies: true, blockSensitiveContent: false, useSimplifiedLanguage: false },
    { mode: "kid_friendly", maxAnswerTokens: 256, temperature: 0.6, includeStories: true, includePanels: false, includeTestimonies: false, includeRoutes: true, preferTestimonies: false, blockSensitiveContent: true, useSimplifiedLanguage: true },
  ];

  for (const mc of modeConfigs) {
    await payload.create({ collection: "ai-mode-configs", data: mc as any });
  }

  await payload.create({
    collection: "ai-safety-settings",
    data: {
      enableHarmSensitivity: true,
      enableTraumaAwareLanguage: true,
      hideGraphicInKidMode: true,
      allowRawTestimonies: false,
      safetyGuidelines: "Always treat genocide-related content with dignity and respect. Never sensationalize. Use trauma-informed language. Acknowledge the gravity of sensitive topics. Prioritize educational value.",
      sensitiveThemes: ["genocide", "violence", "trauma", "death", "massacre", "sexual violence"],
    } as any,
  });

  await payload.create({
    collection: "ai-model-settings",
    data: {
      modelName: "mistral-nemo",
      defaultTemperature: 0.3,
      defaultMaxTokens: 512,
      provider: "ollama",
    } as any,
  });
  console.log("✅ AI configuration seeded (3 tone profiles, 3 mode configs, safety settings)");

  // ── 7. Tour Agency ─────────────────────────────────────
  const agency = await payload.create({
    collection: "tour-agencies",
    data: {
      name: "Rwanda Heritage Tours",
      slug: "rwanda-heritage-tours",
      contactEmail: "info@rwandaheritage.com",
      contactPhone: "+250 788 123 456",
      isActive: true,
      accessTier: "premium",
    } as any,
  });

  await payload.create({
    collection: "agency-pricing-plans",
    data: {
      agency: agency.id,
      name: "Group Day Pass",
      pricePerCode: 15,
      currency: "USD",
      minCodes: 10,
      maxCodes: 100,
      validDays: 1,
      isActive: true,
    } as any,
  });
  console.log("✅ Tour agency + pricing plan created");

  // ── 8. Museum Rooms + Panels (for KGM) ─────────────────
  const kgmId = museumIds["kigali-genocide-memorial"];
  if (kgmId) {
    const room = await payload.create({
      collection: "museum-rooms",
      data: {
        museum: kgmId,
        name: "Before 1994",
        introduction: "This room explores the historical context leading up to the 1994 Genocide against the Tutsi, from colonial-era identity politics to the escalation of violence.",
        roomOrder: 1,
      } as any,
    });

    await payload.create({
      collection: "museum-panels",
      data: {
        room: room.id,
        title: "Colonial Legacy",
        panelNumber: "1",
        panelOrder: 1,
        blocks: [
          { blockType: "text", blockOrder: 1, content: { text: "The colonial period fundamentally altered Rwandan society. Belgian colonial authorities institutionalized ethnic identity through identity cards, creating rigid divisions that would have devastating consequences." } },
          { blockType: "text", blockOrder: 2, content: { text: "Understanding this history is essential to comprehending how the genocide was made possible." } },
        ],
      } as any,
    });
    console.log("✅ KGM room + panel seeded");
  }

  // ── Done ───────────────────────────────────────────────
  console.log("\n🎉 Seed complete!");
  console.log("   Login: admin@muraho.rw / MurahoAdmin2026!");
  console.log(`   Museums: ${museums.length}`);
  console.log(`   Locations: ${locations.length}`);
  console.log(`   Routes: ${routes.length}`);
  console.log(`   Stories: ${stories.length}`);
  console.log("   AI Config: ✅");
  console.log("   Agency: ✅\n");

  process.exit(0);
}

seed().catch((err) => {
  console.error("Seed failed:", err);
  process.exit(1);
});
