export type DemoMode = "search" | "support";
export type DemoSource = "sample" | "live" | "fallback" | "inferred";

export type DemoProduct = {
  id: string;
  name: string;
  brand: string;
  price: number;
  rating: number;
  reviewCount: number;
  tag: string;
  monogram: string;
  tint: string;
};

export type ProductPick = {
  productId: string;
  product?: DemoProduct;
  why: string;
  signals: string[];
};

export type ToolStep = {
  toolName: string;
  args: string;
  result: string;
  durationMs?: number;
};

export type GraphHop = {
  source: string;
  relationship: string;
  target: string;
};

export type KnowledgeChunk = {
  title: string;
  snippet: string;
  score: number;
};

export type MemoryWrite = {
  label: string;
  value: string;
};

export type DemoProfilePrompt = {
  label: string;
  prompt: string;
  mode?: DemoMode;
};

export type DemoProfile = {
  id: string;
  name: string;
  label: string;
  initials: string;
  persona: string;
  chips: string[];
  preferences: { label: string; value: string }[];
  prompts: DemoProfilePrompt[];
};

export type RecentMemoryActivity = {
  id: string;
  kind: "prompt" | "memory_write" | "profile_read" | "tool";
  label: string;
  value: string;
  detail?: string;
  timestamp: number;
};

export type SearchDemoResponse = {
  id: string;
  sessionId?: string;
  source: DemoSource;
  query: string;
  summary: string;
  picks: ProductPick[];
  pairedProductIds: string[];
  profileWrites: MemoryWrite[];
  profileChips: string[];
  tools: ToolStep[];
  graphHops: GraphHop[];
  chunks: KnowledgeChunk[];
  latencyMs: number;
  tokens: number;
  warnings?: string[];
};

export type DiagnosisPathStep = {
  kind: "symptom" | "cause" | "solution";
  label: string;
};

export type CitedSource = {
  kind: "kb" | "ticket" | "review";
  id: string;
  title: string;
  snippet: string;
};

export type SupportDemoResponse = {
  id: string;
  sessionId?: string;
  source: DemoSource;
  query: string;
  summary: string;
  confidence: "high" | "medium" | "low";
  path: DiagnosisPathStep[];
  actions: string[];
  sourceRows: CitedSource[];
  alternativeProductIds: string[];
  tools: ToolStep[];
  latencyMs: number;
  tokens: number;
  warnings?: string[];
};

export type DemoResponse = SearchDemoResponse | SupportDemoResponse;

export const demoProfiles: DemoProfile[] = [
  {
    id: "demo-profile-mara-trail",
    name: "Mara Chen",
    label: "Trail runner",
    initials: "MC",
    persona: "Weekend trail runner shopping for wet-weather routes and durable recovery gear.",
    chips: ["Trail running", "Waterproof", "Under $150"],
    preferences: [
      { label: "activity", value: "trail running" },
      { label: "terrain", value: "rocky weekend routes" },
      { label: "material", value: "waterproof" },
      { label: "budget", value: "under $150" },
    ],
    prompts: [
      {
        label: "Remember trail budget",
        prompt: "Remember that I prefer waterproof trail running shoes under $150 for rocky weekend routes.",
      },
      {
        label: "Recommend shoes",
        prompt: "Now recommend trail running shoes for me based on what you know about my preferences.",
      },
      {
        label: "Recall profile",
        prompt: "What do you remember about my running gear preferences?",
      },
    ],
  },
  {
    id: "demo-profile-owen-fastpack",
    name: "Owen Patel",
    label: "Fastpacker",
    initials: "OP",
    persona: "Fastpacker who values low carried weight, compact shelter systems, and reliable rain protection.",
    chips: ["Ultralight", "Fastpacking", "Compact"],
    preferences: [
      { label: "activity", value: "fastpacking" },
      { label: "priority", value: "low weight" },
      { label: "category", value: "shelter and rain gear" },
      { label: "fit", value: "moves well at speed" },
    ],
    prompts: [
      {
        label: "Remember low weight",
        prompt: "Remember that I prioritize ultralight gear for fastpacking and prefer compact shelters.",
      },
      {
        label: "Build kit",
        prompt: "Recommend a lightweight fastpacking setup for a wet two-day route.",
      },
      {
        label: "Recall profile",
        prompt: "What fastpacking preferences are in my profile?",
      },
    ],
  },
  {
    id: "demo-profile-nina-dayhike",
    name: "Nina Alvarez",
    label: "Day hiker",
    initials: "NA",
    persona: "Day hiker who wants dependable weather protection without carrying bulky gear.",
    chips: ["Day hikes", "Packable", "Rain ready"],
    preferences: [
      { label: "activity", value: "day hiking" },
      { label: "weather", value: "rain" },
      { label: "priority", value: "packability" },
      { label: "brand", value: "Patagonia and Black Diamond" },
    ],
    prompts: [
      {
        label: "Remember rain shell",
        prompt: "Remember that I want packable rain gear for day hikes and prefer Patagonia or Black Diamond.",
      },
      {
        label: "Recommend shell",
        prompt: "Recommend a rain shell and day hike accessories for my profile.",
      },
      {
        label: "Recall profile",
        prompt: "What do you remember about my day hiking preferences?",
      },
    ],
  },
  {
    id: "demo-profile-jules-winter",
    name: "Jules Morgan",
    label: "Winter runner",
    initials: "JM",
    persona: "Cold-weather runner looking for breathable layers and reliable traction.",
    chips: ["Winter running", "Layering", "Traction"],
    preferences: [
      { label: "activity", value: "winter running" },
      { label: "category", value: "base layers and traction" },
      { label: "temperature", value: "below freezing" },
      { label: "priority", value: "breathability" },
    ],
    prompts: [
      {
        label: "Remember cold runs",
        prompt: "Remember that I run in below-freezing weather and prefer breathable cold-weather layers.",
      },
      {
        label: "Recommend layers",
        prompt: "Recommend cold-weather running layers and accessories for me.",
      },
      {
        label: "Recall profile",
        prompt: "What cold-weather running preferences do you remember?",
      },
    ],
  },
  {
    id: "demo-profile-sam-backpack",
    name: "Sam Rivera",
    label: "Budget backpacker",
    initials: "SR",
    persona: "Budget-conscious backpacker comparing tents, pads, and sleeping bags for weekend trips.",
    chips: ["Backpacking", "Budget", "2-person kit"],
    preferences: [
      { label: "activity", value: "backpacking" },
      { label: "capacity", value: "2-person" },
      { label: "budget", value: "under $750 total kit" },
      { label: "priority", value: "value and durability" },
    ],
    prompts: [
      {
        label: "Remember backpacking kit",
        prompt: "Remember that I need a durable two-person backpacking setup under $750.",
      },
      {
        label: "Recommend kit",
        prompt: "Recommend a two-person backpacking setup for my profile.",
      },
      {
        label: "Recall profile",
        prompt: "What backpacking preferences are stored for me?",
      },
    ],
  },
  {
    id: "demo-profile-ari-cushion",
    name: "Ari Brooks",
    label: "Road runner",
    initials: "AB",
    persona: "Road runner who wants neutral, cushioned daily trainers and tracks shoe mileage closely.",
    chips: ["Road running", "Neutral shoe", "Cushion"],
    preferences: [
      { label: "activity", value: "road running" },
      { label: "gait", value: "neutral" },
      { label: "priority", value: "cushion" },
      { label: "replacement", value: "around 300 miles" },
    ],
    prompts: [
      {
        label: "Remember road shoe",
        prompt: "Remember that I prefer neutral cushioned road running shoes and replace them around 300 miles.",
      },
      {
        label: "Recommend trainer",
        prompt: "Recommend daily running shoes for my profile.",
      },
      {
        label: "Diagnose mileage",
        prompt: "My running shoes feel flat after 300 miles. What should I do?",
        mode: "support",
      },
    ],
  },
  {
    id: "demo-profile-tessa-warranty",
    name: "Tessa Nguyen",
    label: "Warranty-focused",
    initials: "TN",
    persona: "Careful shopper who values long warranties, repair guidance, and durable construction.",
    chips: ["Durability", "Warranty", "Repair"],
    preferences: [
      { label: "priority", value: "warranty coverage" },
      { label: "priority", value: "durable construction" },
      { label: "support", value: "repair guidance" },
      { label: "budget", value: "will pay more for longevity" },
    ],
    prompts: [
      {
        label: "Remember warranty",
        prompt: "Remember that I prefer durable gear with strong warranty coverage and clear repair guidance.",
      },
      {
        label: "Recommend durable gear",
        prompt: "Recommend durable outdoor gear for my profile.",
      },
      {
        label: "Diagnose peeling",
        prompt: "The outsole on my running shoes is peeling after 3 months. Is this a warranty issue?",
        mode: "support",
      },
    ],
  },
  {
    id: "demo-profile-liam-family",
    name: "Liam Harper",
    label: "Family camper",
    initials: "LH",
    persona: "Family camper who prefers roomy, easy-to-set-up shelter and comfort over minimum weight.",
    chips: ["Camping", "Comfort", "Easy setup"],
    preferences: [
      { label: "activity", value: "family camping" },
      { label: "priority", value: "comfort" },
      { label: "priority", value: "easy setup" },
      { label: "weight", value: "not ultralight" },
    ],
    prompts: [
      {
        label: "Remember comfort",
        prompt: "Remember that I prefer comfortable family camping gear that is easy to set up.",
      },
      {
        label: "Recommend camp kit",
        prompt: "Recommend camping gear for a comfort-focused family trip.",
      },
      {
        label: "Recall profile",
        prompt: "What camping preferences do you remember about me?",
      },
    ],
  },
  {
    id: "demo-profile-priya-travel",
    name: "Priya Shah",
    label: "Travel hiker",
    initials: "PS",
    persona: "Frequent traveler who wants one-bag compatible hiking gear and compact accessories.",
    chips: ["Travel", "Compact", "Versatile"],
    preferences: [
      { label: "activity", value: "travel hiking" },
      { label: "priority", value: "packable gear" },
      { label: "priority", value: "multi-use products" },
      { label: "constraint", value: "carry-on friendly" },
    ],
    prompts: [
      {
        label: "Remember travel",
        prompt: "Remember that I need carry-on friendly hiking gear that packs small and works across trips.",
      },
      {
        label: "Recommend travel kit",
        prompt: "Recommend compact hiking gear for my travel profile.",
      },
      {
        label: "Recall profile",
        prompt: "What travel gear preferences are in my profile?",
      },
    ],
  },
  {
    id: "demo-profile-ben-gearhead",
    name: "Ben Wallace",
    label: "Gear analyst",
    initials: "BW",
    persona: "Comparison-heavy shopper who wants technical tradeoffs, review patterns, and graph-backed rationale.",
    chips: ["Compare", "Technical", "Evidence"],
    preferences: [
      { label: "shopping_style", value: "comparison-heavy" },
      { label: "priority", value: "technical rationale" },
      { label: "source", value: "reviews and support data" },
      { label: "format", value: "ranked tradeoffs" },
    ],
    prompts: [
      {
        label: "Remember analysis",
        prompt: "Remember that I prefer technical comparisons with review evidence and ranked tradeoffs.",
      },
      {
        label: "Compare tents",
        prompt: "Compare two-person backpacking tents for my profile.",
      },
      {
        label: "Recall profile",
        prompt: "What shopping style preferences do you remember?",
      },
    ],
  },
];

export const products: Record<string, DemoProduct> = {
  mx_master_3s: {
    id: "mx_master_3s",
    name: "MX Master 3S",
    brand: "Logitech",
    price: 99,
    rating: 4.7,
    reviewCount: 4218,
    monogram: "MX",
    tint: "#e8eef7",
    tag: "Ergonomic mouse",
  },
  keychron_m3_pro: {
    id: "keychron_m3_pro",
    name: "M3 Pro Wireless",
    brand: "Keychron",
    price: 79,
    rating: 4.5,
    reviewCount: 612,
    monogram: "M3",
    tint: "#efece4",
    tag: "Wireless mouse",
  },
  logitech_lift: {
    id: "logitech_lift",
    name: "Lift Vertical",
    brand: "Logitech",
    price: 69,
    rating: 4.4,
    reviewCount: 2890,
    monogram: "LV",
    tint: "#ecefe7",
    tag: "Vertical mouse",
  },
  razer_pro_click: {
    id: "razer_pro_click",
    name: "Pro Click Mini",
    brand: "Razer",
    price: 89,
    rating: 4.3,
    reviewCount: 1104,
    monogram: "PC",
    tint: "#efeae6",
    tag: "Compact mouse",
  },
  mouse_pad_xl: {
    id: "mouse_pad_xl",
    name: "Desk Mat XL",
    brand: "Grovemade",
    price: 49,
    rating: 4.8,
    reviewCount: 320,
    monogram: "DM",
    tint: "#ece9e1",
    tag: "Desk mat",
  },
  palm_rest: {
    id: "palm_rest",
    name: "Wood Palm Rest",
    brand: "Grovemade",
    price: 39,
    rating: 4.6,
    reviewCount: 188,
    monogram: "PR",
    tint: "#eee7dc",
    tag: "Palm rest",
  },
  usb_hub: {
    id: "usb_hub",
    name: "Pro Hub 7-in-1",
    brand: "Anker",
    price: 59,
    rating: 4.5,
    reviewCount: 9821,
    monogram: "UH",
    tint: "#e7eaee",
    tag: "USB-C hub",
  },
  bose_qc_ultra: {
    id: "bose_qc_ultra",
    name: "QuietComfort Ultra",
    brand: "Bose",
    price: 429,
    rating: 4.6,
    reviewCount: 1820,
    monogram: "QU",
    tint: "#e8ece8",
    tag: "Over-ear headphones",
  },
  sony_wh1000xm5: {
    id: "sony_wh1000xm5",
    name: "WH-1000XM5",
    brand: "Sony",
    price: 349,
    rating: 4.7,
    reviewCount: 5604,
    monogram: "XM",
    tint: "#e9e9eb",
    tag: "Over-ear headphones",
  },
  sennheiser_momentum_4: {
    id: "sennheiser_momentum_4",
    name: "Momentum 4",
    brand: "Sennheiser",
    price: 349,
    rating: 4.5,
    reviewCount: 1402,
    monogram: "M4",
    tint: "#ece8e3",
    tag: "Over-ear headphones",
  },
  travel_case: {
    id: "travel_case",
    name: "Compact Travel Case",
    brand: "Peak Design",
    price: 39,
    rating: 4.7,
    reviewCount: 410,
    monogram: "TC",
    tint: "#eae7e0",
    tag: "Accessory",
  },
  flight_adapter: {
    id: "flight_adapter",
    name: "Airplane Audio Adapter",
    brand: "Twelve South",
    price: 19,
    rating: 4.4,
    reviewCount: 232,
    monogram: "AA",
    tint: "#ebe9e3",
    tag: "Accessory",
  },
  brooks_cascadia_17_gtx: {
    id: "brooks_cascadia_17_gtx",
    name: "Cascadia 17 GTX",
    brand: "Brooks",
    price: 149,
    rating: 4.6,
    reviewCount: 1280,
    monogram: "C17",
    tint: "#e6efe8",
    tag: "Trail running shoes",
  },
  nike_pegasus_trail_4_gtx: {
    id: "nike_pegasus_trail_4_gtx",
    name: "Pegasus Trail 4 GTX",
    brand: "Nike",
    price: 140,
    rating: 4.5,
    reviewCount: 2150,
    monogram: "PT",
    tint: "#e8edf1",
    tag: "Road-to-trail shoes",
  },
  hoka_speedgoat_5: {
    id: "hoka_speedgoat_5",
    name: "Speedgoat 5",
    brand: "Hoka",
    price: 155,
    rating: 4.7,
    reviewCount: 3340,
    monogram: "SG",
    tint: "#eee8df",
    tag: "Technical trail shoes",
  },
  darn_tough_trail_socks: {
    id: "darn_tough_trail_socks",
    name: "Trail Midweight Socks",
    brand: "Darn Tough",
    price: 25,
    rating: 4.8,
    reviewCount: 912,
    monogram: "DT",
    tint: "#e9ede6",
    tag: "Trail socks",
  },
  black_diamond_stormline: {
    id: "black_diamond_stormline",
    name: "Stormline Stretch Rain Shell",
    brand: "Black Diamond",
    price: 169,
    rating: 4.5,
    reviewCount: 740,
    monogram: "BD",
    tint: "#e6ebef",
    tag: "Rain jacket",
  },
  patagonia_torrentshell: {
    id: "patagonia_torrentshell",
    name: "Torrentshell 3L",
    brand: "Patagonia",
    price: 179,
    rating: 4.6,
    reviewCount: 1810,
    monogram: "PT",
    tint: "#e9ece5",
    tag: "Rain jacket",
  },
  osprey_daylite: {
    id: "osprey_daylite",
    name: "Daylite Pack",
    brand: "Osprey",
    price: 65,
    rating: 4.7,
    reviewCount: 2640,
    monogram: "OD",
    tint: "#e8e7df",
    tag: "Day pack",
  },
  "ua-coldgear": {
    id: "ua-coldgear",
    name: "ColdGear Base Layer",
    brand: "Under Armour",
    price: 55,
    rating: 4.2,
    reviewCount: 4,
    monogram: "CG",
    tint: "#e8edf1",
    tag: "Winter running layer",
  },
  "nike-drifit-tee": {
    id: "nike-drifit-tee",
    name: "Dri-FIT Running Shirt",
    brand: "Nike",
    price: 35,
    rating: 4.1,
    reviewCount: 4,
    monogram: "DF",
    tint: "#e9ede6",
    tag: "Moisture-wicking tee",
  },
  "adidas-running-shorts": {
    id: "adidas-running-shorts",
    name: "Running Shorts",
    brand: "Adidas",
    price: 30,
    rating: 4.0,
    reviewCount: 4,
    monogram: "AR",
    tint: "#efece4",
    tag: "AEROREADY shorts",
  },
  "nike-running-socks": {
    id: "nike-running-socks",
    name: "Multiplier Running Socks",
    brand: "Nike",
    price: 18,
    rating: 4.2,
    reviewCount: 4,
    monogram: "NS",
    tint: "#ecefe7",
    tag: "Dri-FIT socks",
  },
  "asics-gel-nimbus-26": {
    id: "asics-gel-nimbus-26",
    name: "Gel-Nimbus 26",
    brand: "ASICS",
    price: 160,
    rating: 3.0,
    reviewCount: 4,
    monogram: "GN",
    tint: "#e8eef7",
    tag: "Max cushion running shoe",
  },
  "nike-pegasus-40": {
    id: "nike-pegasus-40",
    name: "Pegasus 40",
    brand: "Nike",
    price: 130,
    rating: 3.5,
    reviewCount: 4,
    monogram: "P40",
    tint: "#e8edf1",
    tag: "Daily trainer",
  },
  "adidas-ultraboost-24": {
    id: "adidas-ultraboost-24",
    name: "Ultraboost 24",
    brand: "Adidas",
    price: 190,
    rating: 3.25,
    reviewCount: 4,
    monogram: "UB",
    tint: "#efece4",
    tag: "High-cushion trainer",
  },
  "brooks-ghost-16": {
    id: "brooks-ghost-16",
    name: "Ghost 16",
    brand: "Brooks",
    price: 140,
    rating: 3.5,
    reviewCount: 4,
    monogram: "G16",
    tint: "#e6efe8",
    tag: "Neutral running shoe",
  },
  "garmin-forerunner-265": {
    id: "garmin-forerunner-265",
    name: "Forerunner 265",
    brand: "Garmin",
    price: 450,
    rating: 3.5,
    reviewCount: 4,
    monogram: "FR",
    tint: "#e7eaee",
    tag: "GPS running watch",
  },
  "rei-half-dome-tent": {
    id: "rei-half-dome-tent",
    name: "Half Dome SL 2+ Tent",
    brand: "REI Co-op",
    price: 279,
    rating: 3.5,
    reviewCount: 4,
    monogram: "HD",
    tint: "#e6efe8",
    tag: "2-person tent",
  },
  "msr-hubba-hubba-tent": {
    id: "msr-hubba-hubba-tent",
    name: "Hubba Hubba NX 2 Tent",
    brand: "MSR",
    price: 450,
    rating: 3.5,
    reviewCount: 4,
    monogram: "HH",
    tint: "#e6ebef",
    tag: "Ultralight tent",
  },
  "nemo-disco-sleeping-bag": {
    id: "nemo-disco-sleeping-bag",
    name: "Disco 30 Sleeping Bag",
    brand: "NEMO",
    price: 219.95,
    rating: 3.5,
    reviewCount: 4,
    monogram: "ND",
    tint: "#eae7e0",
    tag: "Synthetic sleeping bag",
  },
  "kelty-cosmic-sleeping-bag": {
    id: "kelty-cosmic-sleeping-bag",
    name: "Cosmic 20 Down Sleeping Bag",
    brand: "Kelty",
    price: 129.95,
    rating: 3.5,
    reviewCount: 4,
    monogram: "KC",
    tint: "#eee8df",
    tag: "Budget down bag",
  },
  "therm-a-rest-sleeping-pad": {
    id: "therm-a-rest-sleeping-pad",
    name: "NeoAir XTherm Sleeping Pad",
    brand: "Therm-a-Rest",
    price: 229.95,
    rating: 3.5,
    reviewCount: 4,
    monogram: "TR",
    tint: "#e9e9eb",
    tag: "4-season sleeping pad",
  },
};

export const searchSamples: SearchDemoResponse[] = [
  {
    id: "trail_running_shoes",
    source: "sample",
    query: "waterproof trail running shoes under $150 for rocky weekend runs",
    summary:
      "Three picks weighted toward waterproofing, trail grip, and price discipline.",
    picks: [
      {
        productId: "brooks_cascadia_17_gtx",
        why: "Best balance of waterproof protection, stable footing, and a price that stays under the stated cap.",
        signals: ["waterproof", "trail grip", "under $150"],
      },
      {
        productId: "nike_pegasus_trail_4_gtx",
        why: "Lighter road-to-trail feel with enough weather protection for wet weekend routes.",
        signals: ["waterproof", "road-to-trail", "lightweight"],
      },
      {
        productId: "hoka_speedgoat_5",
        why: "More cushion and traction for technical routes, but it may sit slightly above the target budget.",
        signals: ["max cushion", "technical trail", "budget stretch"],
      },
    ],
    pairedProductIds: ["darn_tough_trail_socks", "osprey_daylite", "black_diamond_stormline"],
    profileWrites: [
      { label: "activity", value: "trail running" },
      { label: "material", value: "waterproof" },
      { label: "budget.cap_usd", value: "150" },
    ],
    profileChips: ["Trail runner", "Waterproof preferred", "Budget under $150"],
    tools: [
      {
        toolName: "search_products",
        args: "waterproof trail running shoes under 150",
        result: "10 results, top score 0.91",
        durationMs: 220,
      },
      {
        toolName: "hybrid_knowledge_search",
        args: "trail shoes waterproof grip mileage",
        result: "4 chunks, top score 0.84",
        durationMs: 280,
      },
      {
        toolName: "get_related_products",
        args: "similar shoes and trail accessories",
        result: "7 nodes returned",
        durationMs: 180,
      },
      {
        toolName: "track_preference",
        args: "3 keys",
        result: "committed to long-term memory",
        durationMs: 120,
      },
    ],
    graphHops: [
      { source: "Query", relationship: "INTENT", target: "trail running, waterproof, budget" },
      { source: "Product", relationship: "BRAND", target: "Brooks, Nike, Hoka" },
      { source: "Product", relationship: "HAS_FEATURE", target: "waterproof upper, trail lugs" },
      { source: "Product", relationship: "BOUGHT_TOGETHER", target: "trail socks, day pack" },
    ],
    chunks: [
      {
        title: "Trail guide wet-weather shoe selection",
        snippet: "Waterproof uppers help in wet grass and cold rain, while aggressive lugs matter more on rocky climbs.",
        score: 0.84,
      },
      {
        title: "Review cluster Cascadia 17 GTX",
        snippet: "Runners liked the stable platform for rocky weekend routes and wet shoulder-season trails.",
        score: 0.79,
      },
      {
        title: "Support note outsole traction and mileage",
        snippet: "Trail shoes should be inspected around 300 miles for compressed foam and worn lugs.",
        score: 0.72,
      },
    ],
    latencyMs: 1410,
    tokens: 3812,
    warnings: ["Sample response while backend structured trace work is in progress."],
  },
  {
    id: "rain_hiking_jacket",
    source: "sample",
    query: "lightweight rain jacket for day hikes that packs small",
    summary:
      "Three picks weighted toward waterproofing, packability, and day-hike comfort.",
    picks: [
      {
        productId: "black_diamond_stormline",
        why: "Light, packable, and stretchy enough for active hiking without feeling overbuilt.",
        signals: ["waterproof", "packable", "stretch"],
      },
      {
        productId: "patagonia_torrentshell",
        why: "More durable three-layer shell for wetter trips where longevity matters.",
        signals: ["waterproof", "durable", "3-layer"],
      },
      {
        productId: "osprey_daylite",
        why: "Useful paired day pack with room for a shell, snacks, and layers.",
        signals: ["paired gear", "day hike", "packable"],
      },
    ],
    pairedProductIds: ["osprey_daylite", "darn_tough_trail_socks", "brooks_cascadia_17_gtx"],
    profileWrites: [
      { label: "activity", value: "day hiking" },
      { label: "priority.portability", value: "high" },
      { label: "weather", value: "rain" },
    ],
    profileChips: ["Day hiker", "Portability first", "Rain ready"],
    tools: [
      {
        toolName: "search_products",
        args: "lightweight rain jacket day hikes packable",
        result: "14 results, top score 0.88",
        durationMs: 220,
      },
      {
        toolName: "knowledge_search",
        args: "rain shell waterproof packability day hikes",
        result: "6 chunks, top score 0.81",
        durationMs: 280,
      },
      {
        toolName: "get_related_products",
        args: "rain shell hiking accessories",
        result: "12 attributes diffed",
        durationMs: 240,
      },
      {
        toolName: "track_preference",
        args: "3 keys",
        result: "committed to long-term memory",
        durationMs: 120,
      },
    ],
    graphHops: [
      { source: "Query", relationship: "INTENT", target: "day hiking, rain, packable" },
      { source: "Product", relationship: "HAS_FEATURE", target: "waterproof, breathable" },
      { source: "Product", relationship: "CITED_IN", target: "Rain shell guide, reviews" },
      { source: "Product", relationship: "SIMILAR_TO", target: "6 alternatives" },
    ],
    chunks: [
      {
        title: "Rain shell guide for day hikes",
        snippet: "Packability and breathability matter most when a shell spends more time in a day pack than on body.",
        score: 0.81,
      },
      {
        title: "Review cluster Stormline Stretch",
        snippet: "Stretch fabric helps with scrambling and fast hiking without adding much bulk.",
        score: 0.77,
      },
      {
        title: "Layering note shoulder-season hiking",
        snippet: "A light rain shell pairs well with a thin insulating layer for variable mountain weather.",
        score: 0.74,
      },
    ],
    latencyMs: 1620,
    tokens: 4204,
    warnings: ["Sample response while backend structured trace work is in progress."],
  },
  {
    id: "cold_weather_layers",
    source: "sample",
    query: "Recommend cold-weather running gear with moisture-wicking layers.",
    summary:
      "A winter running kit centered on warm compression, moisture movement, and dry feet.",
    picks: [
      {
        productId: "ua-coldgear",
        why: "Primary cold-weather layer with dual-layer warmth and a compression fit for winter runs.",
        signals: ["ColdGear", "warm base layer", "compression fit"],
      },
      {
        productId: "nike-drifit-tee",
        why: "Light moisture-wicking layer that can sit under or over the base layer depending on conditions.",
        signals: ["Dri-FIT", "polyester", "moisture wicking"],
      },
      {
        productId: "nike-running-socks",
        why: "Cushioned Dri-FIT socks keep the moisture-wicking story consistent down to the feet.",
        signals: ["Dri-FIT", "arch support", "cushioned"],
      },
    ],
    pairedProductIds: ["adidas-running-shorts", "nike-pegasus-40", "garmin-forerunner-265"],
    profileWrites: [
      { label: "activity", value: "cold-weather running" },
      { label: "material", value: "moisture-wicking synthetic" },
      { label: "fit", value: "compression base layer" },
    ],
    profileChips: ["Winter runner", "Moisture-wicking layers", "Synthetic fabric care"],
    tools: [
      {
        toolName: "search_products",
        args: "cold-weather running moisture-wicking layers",
        result: "4 live catalog products matched",
        durationMs: 210,
      },
      {
        toolName: "knowledge_search",
        args: "ColdGear Dri-FIT fabric softener moisture wicking",
        result: "3 care and review chunks",
        durationMs: 260,
      },
      {
        toolName: "get_related_products",
        args: "apparel and running accessories",
        result: "paired apparel and sock nodes",
        durationMs: 150,
      },
    ],
    graphHops: [
      { source: "Query", relationship: "INTENT", target: "cold weather, running, moisture management" },
      { source: "Under Armour ColdGear Base Layer", relationship: "HAS_ATTRIBUTE", target: "compression fit" },
      { source: "Nike Dri-FIT Running Shirt", relationship: "HAS_FEATURE", target: "moisture wicking" },
      { source: "Nike Pegasus 40", relationship: "BOUGHT_TOGETHER", target: "Nike Multiplier Running Socks" },
    ],
    chunks: [
      {
        title: "ColdGear warmth and wicking",
        snippet: "ColdGear keeps runners warm around 30F when layered with a wind shell, while moisture wicking depends on avoiding fabric softener.",
        score: 0.86,
      },
      {
        title: "Dri-FIT care guidance",
        snippet: "Fabric softener can reduce moisture-wicking performance; vinegar wash can restore some function.",
        score: 0.8,
      },
      {
        title: "Running sock fit notes",
        snippet: "Cushioned Dri-FIT socks add arch support and help keep feet dry on cold runs.",
        score: 0.75,
      },
    ],
    latencyMs: 1320,
    tokens: 3180,
    warnings: ["Sample response while backend structured trace work is in progress."],
  },
  {
    id: "backpacking_tent_comparison",
    source: "sample",
    query: "Compare the REI Half Dome SL 2+ and MSR Hubba Hubba NX for backpacking.",
    summary:
      "The REI tent favors price and livability, while the MSR tent favors lower weight and premium backpacking design.",
    picks: [
      {
        productId: "rei-half-dome-tent",
        why: "Better value for two people who want room, simple setup, and a lower tent budget.",
        signals: ["$279", "roomy", "color-coded setup"],
      },
      {
        productId: "msr-hubba-hubba-tent",
        why: "Better for weight-conscious backpackers who value two doors, two vestibules, and faster setup.",
        signals: ["1.54kg", "two vestibules", "premium"],
      },
    ],
    pairedProductIds: ["nemo-disco-sleeping-bag", "kelty-cosmic-sleeping-bag", "therm-a-rest-sleeping-pad"],
    profileWrites: [
      { label: "activity", value: "backpacking" },
      { label: "capacity", value: "2-person tent" },
      { label: "comparison", value: "value vs ultralight" },
    ],
    profileChips: ["Backpacking", "2-person shelter", "Compares value vs weight"],
    tools: [
      {
        toolName: "search_products",
        args: "REI Half Dome MSR Hubba Hubba backpacking tent",
        result: "2 tent products matched",
        durationMs: 200,
      },
      {
        toolName: "knowledge_search",
        args: "Half Dome Hubba Hubba rainfly condensation pole hub weight",
        result: "5 review and support chunks",
        durationMs: 300,
      },
      {
        toolName: "get_related_products",
        args: "tent sleeping bag sleeping pad",
        result: "3 bought-together products",
        durationMs: 170,
      },
    ],
    graphHops: [
      { source: "REI Half Dome SL 2+ Tent", relationship: "SIMILAR_TO", target: "MSR Hubba Hubba NX 2 Tent" },
      { source: "REI Half Dome SL 2+ Tent", relationship: "BOUGHT_TOGETHER", target: "NEMO Disco 30 Sleeping Bag" },
      { source: "MSR Hubba Hubba NX 2 Tent", relationship: "BOUGHT_TOGETHER", target: "Therm-a-Rest NeoAir XTherm Sleeping Pad" },
    ],
    chunks: [
      {
        title: "REI Half Dome field feedback",
        snippet: "Reviews call out heavy-rain performance and livability, with some condensation and pole sleeve concerns.",
        score: 0.83,
      },
      {
        title: "MSR Hubba Hubba field feedback",
        snippet: "Reviews praise the low weight, two-door layout, and fast setup, while noting rainfly pooling and pole hub issues.",
        score: 0.81,
      },
      {
        title: "Tent bundle graph",
        snippet: "Both tent products are connected to sleeping bags and a high R-value sleeping pad through bought-together relationships.",
        score: 0.76,
      },
    ],
    latencyMs: 1480,
    tokens: 3550,
    warnings: ["Sample response while backend structured trace work is in progress."],
  },
  {
    id: "two_person_backpacking_setup",
    source: "sample",
    query: "Build a 2-person backpacking setup with a tent, sleeping bag, and pad under $750.",
    summary:
      "A value-focused setup fits under $750 by pairing the REI tent, Kelty down bag, and Therm-a-Rest pad.",
    picks: [
      {
        productId: "rei-half-dome-tent",
        why: "Keeps the shelter cost controlled while still providing a roomy two-person backpacking tent.",
        signals: ["2-person", "$279", "3-season"],
      },
      {
        productId: "kelty-cosmic-sleeping-bag",
        why: "Budget-friendly 20F down bag that keeps the total bundle below the cap.",
        signals: ["20F", "$129.95", "550-fill down"],
      },
      {
        productId: "therm-a-rest-sleeping-pad",
        why: "High R-value pad rounds out the sleep system while keeping the total near $639.",
        signals: ["R-value 6.9", "$229.95", "4-season pad"],
      },
    ],
    pairedProductIds: ["nemo-disco-sleeping-bag", "msr-hubba-hubba-tent"],
    profileWrites: [
      { label: "activity", value: "2-person backpacking" },
      { label: "budget.cap_usd", value: "750" },
      { label: "bundle", value: "tent + sleeping bag + pad" },
    ],
    profileChips: ["2-person backpacking", "Budget under $750", "Sleep system bundle"],
    tools: [
      {
        toolName: "search_products",
        args: "2-person backpacking tent sleeping bag sleeping pad under 750",
        result: "5 outdoor equipment products matched",
        durationMs: 230,
      },
      {
        toolName: "get_related_products",
        args: "REI Half Dome bought together sleeping bag pad",
        result: "4 bundle relationships",
        durationMs: 180,
      },
      {
        toolName: "knowledge_search",
        args: "backpacking tent sleeping bag pad condensation warmth",
        result: "4 support chunks",
        durationMs: 280,
      },
    ],
    graphHops: [
      { source: "REI Half Dome SL 2+ Tent", relationship: "BOUGHT_TOGETHER", target: "Kelty Cosmic 20 Down Sleeping Bag" },
      { source: "REI Half Dome SL 2+ Tent", relationship: "BOUGHT_TOGETHER", target: "Therm-a-Rest NeoAir XTherm Sleeping Pad" },
      { source: "Bundle", relationship: "TOTAL_PRICE", target: "$638.90" },
    ],
    chunks: [
      {
        title: "Backpacking sleep system value",
        snippet: "The Kelty Cosmic is the budget warmth pick, while the Therm-a-Rest pad provides the strongest warmth-to-weight floor insulation.",
        score: 0.84,
      },
      {
        title: "Condensation risk note",
        snippet: "Tent condensation can dampen down bags, so the setup should include ventilation discipline and a dry bag.",
        score: 0.78,
      },
      {
        title: "Bundle total",
        snippet: "REI Half Dome ($279), Kelty Cosmic ($129.95), and Therm-a-Rest XTherm ($229.95) total $638.90.",
        score: 0.74,
      },
    ],
    latencyMs: 1540,
    tokens: 3720,
    warnings: ["Sample response while backend structured trace work is in progress."],
  },
];

export const supportSamples: SupportDemoResponse[] = [
  {
    id: "shoes_flat",
    source: "sample",
    query: "My running shoes feel flat and unresponsive after 300 miles. What should I do?",
    summary:
      "Likely midsole compression from high mileage. Knowledge chunks and reviews point to replacement or rotation.",
    confidence: "high",
    path: [
      { kind: "symptom", label: "Flat ride after 300 miles" },
      { kind: "cause", label: "Compressed midsole foam and worn lugs" },
      { kind: "solution", label: "Rotate or replace shoes" },
    ],
    actions: [
      "Inspect outsole lugs and midsole creasing before the next long run.",
      "Rotate in a fresh pair for workouts and long runs.",
      "Keep the old pair only for short easy runs if traction is still safe.",
    ],
    sourceRows: [
      {
        kind: "kb",
        id: "KB-301",
        title: "Running shoe midsole life",
        snippet: "Foam compression commonly appears between 300 and 500 miles depending on surface and runner load.",
      },
      {
        kind: "ticket",
        id: "#4421",
        title: "Trail runner reported flat ride",
        snippet: "Support recommended replacement after visible midsole creasing and reduced rebound.",
      },
      {
        kind: "review",
        id: "Review cluster midsole fatigue",
        title: "Cushioning loss after heavy mileage",
        snippet: "Reviews describe a flatter ride once the shoe passes the high-mileage threshold.",
      },
    ],
    alternativeProductIds: ["brooks_cascadia_17_gtx", "nike_pegasus_trail_4_gtx", "hoka_speedgoat_5"],
    tools: [
      {
        toolName: "hybrid_knowledge_search",
        args: "running shoes flat unresponsive 300 miles",
        result: "6 chunks, top score 0.87",
        durationMs: 240,
      },
      {
        toolName: "diagnose_product_issue",
        args: "midsole compression",
        result: "2 causes weighted",
        durationMs: 180,
      },
      {
        toolName: "knowledge_search",
        args: "shoe mileage replacement guidance",
        result: "1 solution cited 3 times",
        durationMs: 200,
      },
      {
        toolName: "get_related_products",
        args: "replacement trail shoes",
        result: "3 alternatives",
        durationMs: 160,
      },
    ],
    latencyMs: 1280,
    tokens: 2940,
    warnings: ["Sample response while backend structured trace work is in progress."],
  },
  {
    id: "outsole_peeling",
    source: "sample",
    query: "The Continental outsole on my trail shoes is peeling after three months.",
    summary:
      "Peeling outsole after a short ownership window points to adhesion failure, heat drying, or high-flex wear.",
    confidence: "high",
    path: [
      { kind: "symptom", label: "Outsole peeling after three months" },
      { kind: "cause", label: "Adhesion failure or high-flex wear" },
      { kind: "solution", label: "Stop heat drying and start warranty review" },
    ],
    actions: [
      "Clean and dry the outsole area without heat.",
      "Photograph the separation width and purchase date.",
      "Start a support claim if the peeling is wider than a few millimeters.",
    ],
    sourceRows: [
      {
        kind: "kb",
        id: "KB-514",
        title: "Trail shoe outsole separation",
        snippet: "Heat drying and repeated high-flex stress can weaken outsole adhesive.",
      },
      {
        kind: "ticket",
        id: "#5102",
        title: "Short-window outsole claim",
        snippet: "Three-month outsole separation was routed to warranty after photos confirmed adhesive failure.",
      },
      {
        kind: "review",
        id: "Reviews outsole durability",
        title: "Peeling reports after wet runs",
        snippet: "Several reviews connect heat drying after wet runs with early outsole separation.",
      },
    ],
    alternativeProductIds: ["brooks_cascadia_17_gtx", "hoka_speedgoat_5"],
    tools: [
      {
        toolName: "hybrid_knowledge_search",
        args: "Continental outsole peeling after 3 months",
        result: "5 chunks, top score 0.83",
        durationMs: 240,
      },
      {
        toolName: "diagnose_product_issue",
        args: "outsole peeling",
        result: "1 cause weighted",
        durationMs: 160,
      },
      {
        toolName: "knowledge_search",
        args: "outsole separation warranty",
        result: "2 actions cited",
        durationMs: 200,
      },
    ],
    latencyMs: 980,
    tokens: 2102,
    warnings: ["Sample response while backend structured trace work is in progress."],
  },
  {
    id: "tent_condensation",
    source: "sample",
    query: "My REI Half Dome tent has condensation every morning and my sleeping bag gets damp.",
    summary:
      "Morning condensation points to ventilation and moisture management, with extra risk for down sleeping bags.",
    confidence: "high",
    path: [
      { kind: "symptom", label: "Condensation on inner tent walls" },
      { kind: "cause", label: "Moisture buildup inside the tent despite rainfly protection" },
      { kind: "solution", label: "Open vents and protect the bag in a waterproof dry bag" },
    ],
    actions: [
      "Open roof and door vents whenever weather allows, even during light rain.",
      "Avoid pressing the sleeping bag against tent walls where condensation collects.",
      "Store down bags in a waterproof dry bag inside the tent and dry them fully after the trip.",
    ],
    sourceRows: [
      {
        kind: "review",
        id: "R-067",
        title: "REI Half Dome condensation review",
        snippet: "Condensation appeared every morning and dampened a Kelty Cosmic down bag; opening vents helped but did not eliminate it.",
      },
      {
        kind: "kb",
        id: "KA-057",
        title: "Half Dome condensation troubleshooting",
        snippet: "Ventilation and site choice reduce condensation, but damp conditions can still require bag protection.",
      },
      {
        kind: "ticket",
        id: "T-057",
        title: "Wet sleeping bag in tent",
        snippet: "Support recommended venting the shelter and keeping the sleeping bag away from tent walls.",
      },
    ],
    alternativeProductIds: ["nemo-disco-sleeping-bag", "kelty-cosmic-sleeping-bag", "therm-a-rest-sleeping-pad"],
    tools: [
      {
        toolName: "hybrid_knowledge_search",
        args: "REI Half Dome condensation sleeping bag damp",
        result: "5 chunks, top score 0.88",
        durationMs: 250,
      },
      {
        toolName: "diagnose_product_issue",
        args: "rei-half-dome-tent condensation damp sleeping bag",
        result: "ventilation and bag protection solutions",
        durationMs: 190,
      },
      {
        toolName: "knowledge_search",
        args: "down sleeping bag condensation dry bag",
        result: "related sleeping bag moisture context",
        durationMs: 210,
      },
    ],
    latencyMs: 1210,
    tokens: 2860,
    warnings: ["Sample response while backend structured trace work is in progress."],
  },
  {
    id: "sleeping_pad_deflated",
    source: "sample",
    query: "My Therm-a-Rest pad deflated overnight. How should I troubleshoot it?",
    summary:
      "Overnight deflation is most likely a pinhole leak or valve contamination; isolate the leak before the next trip.",
    confidence: "high",
    path: [
      { kind: "symptom", label: "Sleeping pad deflated overnight" },
      { kind: "cause", label: "Pinhole leak or debris in the valve" },
      { kind: "solution", label: "Submerge, mark, patch, and clean the valve" },
    ],
    actions: [
      "Inflate the pad fully and listen around the valve before checking the pad body.",
      "Submerge sections in water or use soapy water to find bubbles, then mark the leak.",
      "Use the included repair kit for pinholes; rinse sand or grit from the valve if air escapes there.",
    ],
    sourceRows: [
      {
        kind: "review",
        id: "R-083",
        title: "NeoAir XTherm pinhole leak review",
        snippet: "A customer woke up on the ground after overnight deflation and reported that the repair kit worked.",
      },
      {
        kind: "kb",
        id: "KA-083",
        title: "Sleeping pad leak diagnosis",
        snippet: "Pinhole leaks are found by submerging the inflated pad or applying soapy water and watching for bubbles.",
      },
      {
        kind: "kb",
        id: "KA-084",
        title: "Valve debris troubleshooting",
        snippet: "Sand or dirt in the valve mechanism can cause air to hiss from the valve even when closed.",
      },
    ],
    alternativeProductIds: ["therm-a-rest-sleeping-pad"],
    tools: [
      {
        toolName: "hybrid_knowledge_search",
        args: "Therm-a-Rest pad deflated overnight pinhole valve",
        result: "4 chunks, top score 0.9",
        durationMs: 230,
      },
      {
        toolName: "diagnose_product_issue",
        args: "therm-a-rest-sleeping-pad deflated overnight",
        result: "leak and valve troubleshooting path",
        durationMs: 180,
      },
      {
        toolName: "knowledge_search",
        args: "sleeping pad repair kit valve debris",
        result: "2 solutions cited",
        durationMs: 200,
      },
    ],
    latencyMs: 1090,
    tokens: 2510,
    warnings: ["Sample response while backend structured trace work is in progress."],
  },
  {
    id: "gel_nimbus_lump",
    source: "sample",
    query: "The ASICS Gel-Nimbus 26 has a hard lump under the heel. Is it a defect?",
    summary:
      "A hard heel lump from day one maps to the PureGEL uneven-insert issue and can indicate a manufacturing defect.",
    confidence: "high",
    path: [
      { kind: "symptom", label: "Hard lump under the heel" },
      { kind: "cause", label: "Debris under the insole or deformed PureGEL insert" },
      { kind: "solution", label: "Check under the insole, then contact ASICS if the midsole is deformed" },
    ],
    actions: [
      "Remove the OrthoLite insole and check for debris or a folded insole edge.",
      "If the midsole itself feels uneven after reseating the insole, stop running in the shoe.",
      "Contact ASICS for replacement because a deformed PureGEL insert is treated as a defect.",
    ],
    sourceRows: [
      {
        kind: "kb",
        id: "KA-015",
        title: "PureGEL Insert Feels Uneven",
        snippet: "If the midsole itself is deformed, this is a manufacturing defect and ASICS should be contacted for replacement.",
      },
      {
        kind: "review",
        id: "R-016",
        title: "Gel-Nimbus hard heel lump review",
        snippet: "A customer felt a hard lump under the heel from day one and returned the shoe.",
      },
      {
        kind: "ticket",
        id: "T-016",
        title: "Gel-Nimbus heel insert complaint",
        snippet: "Support asked the customer to inspect the insole, then routed the case as a defect when the midsole remained uneven.",
      },
    ],
    alternativeProductIds: ["brooks-ghost-16", "nike-pegasus-40", "adidas-ultraboost-24"],
    tools: [
      {
        toolName: "hybrid_knowledge_search",
        args: "ASICS Gel-Nimbus 26 hard lump heel PureGEL defect",
        result: "4 chunks, top score 0.91",
        durationMs: 240,
      },
      {
        toolName: "diagnose_product_issue",
        args: "asics-gel-nimbus-26 hard lump under heel",
        result: "defect path with replacement guidance",
        durationMs: 170,
      },
      {
        toolName: "get_related_products",
        args: "neutral running shoe alternatives",
        result: "3 similar running shoes",
        durationMs: 160,
      },
    ],
    latencyMs: 1160,
    tokens: 2680,
    warnings: ["Sample response while backend structured trace work is in progress."],
  },
];
