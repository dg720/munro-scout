import "leaflet/dist/leaflet.css";
import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import {
  Box, Heading, Text, Input, Flex, SimpleGrid, Button,
  Alert, AlertIcon, Tag as CTag, TagLabel, HStack, Spinner
} from "@chakra-ui/react";
import { MapContainer, TileLayer } from "react-leaflet";

import { Munro } from "../../types/munro";
import { prettyLabel } from "../../utils/labels";
import { useSelectedGpxUrl } from "../../hooks/useSelectedGpxUrl";
import { DEFAULT_CENTER } from "../../config/constants";
import MapRefStash from "../../components/map/MapRefStash";
import GpxOverlay from "../../components/map/GpxOverlay";

type Props = { initialMunro: Munro | null };

// Optional extension: munros may already include `tags`
type MunroWithTags = Munro & { tags?: string[] };

const API_BASE =
  (typeof process !== "undefined" && (process as any)?.env?.REACT_APP_API_BASE) ||
  "http://localhost:5000";

// Mirror of your ONTOLOGY (flat, one-word tags)
const ALLOWED_TAGS = new Set<string>([
  // terrain
  "ridge","scramble","technical","steep","rocky","boggy","heather","scree","handson","knifeedge","airy","slab","gully",
  // difficulty
  "easy","moderate","hard","serious",
  // nav
  "pathless",
  // hazards
  "loose_rock","cornice","river_crossing","slippery","exposure",
  // access
  "bus","train","bike",
  // features
  "classic","views","waterfalls","bothy","scrambling","camping","multiday",
  // crowding
  "popular","quiet",
  // suitability
  "family",
]);

export default function DetailsTab({ initialMunro }: Props) {
  const [query, setQuery] = useState("");
  const [options, setOptions] = useState<MunroWithTags[]>([]);
  const [selected, setSelected] = useState<MunroWithTags | null>(null);
  const [showDropdown, setShowDropdown] = useState(false);
  const [gpxError, setGpxError] = useState<string | null>(null);

  // Dynamic tags state
  const [tags, setTags] = useState<string[] | null>(null);
  const [tagsLoading, setTagsLoading] = useState(false);
  const [tagsError, setTagsError] = useState<string | null>(null);
  const [tagsWarning, setTagsWarning] = useState<string | null>(null);

  useEffect(() => {
    if (initialMunro) {
      setSelected(initialMunro as MunroWithTags);
      setQuery(initialMunro.name);
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  }, [initialMunro]);

  // Search munros by name
  useEffect(() => {
    if (!query.trim()) {
      setOptions([]);
      return;
    }
    axios
      .get(`${API_BASE}/api/munros?search=${encodeURIComponent(query)}`)
      .then((res) => {
        const list = res.data as MunroWithTags[];
        const filtered = list.filter((m) =>
          m.name.toLowerCase().includes(query.toLowerCase())
        );
        setOptions(filtered);
        setShowDropdown(true);
      })
      .catch((err) => console.error(err));
  }, [query]);

  const handleSelect = (munro: MunroWithTags) => {
    setSelected(munro);
    setQuery(munro.name);
    setOptions([]);
    setShowDropdown(false);
    setGpxError(null);
  };

  const openInNew = (url: string) => window.open(url, "_blank", "noopener,noreferrer");

  // Hide these from Additional Details
  const CORE_FIELDS = useMemo(
    () =>
      new Set([
        "id","name","summary","distance","time","grade","bog","start",
        "title","terrain","public_transport","description",
        "gpx_file","url","route_url","tags"
      ]),
    []
  );

  // ---- Helpers to normalise/sanitise tag payloads ----
  const tokenizeStringTags = (raw: string): string[] => {
    // Split by commas/semicolons/pipes/whitespace but NOT underscores (to preserve 'river_crossing' & 'loose_rock')
    return raw
      .split(/[,\s;|]+/)
      .map(s => s.trim().toLowerCase())
      .filter(Boolean);
  };

  const sanitizeTags = (data: any): string[] => {
    setTagsWarning(null);

    let out: string[] = [];

    if (Array.isArray(data) && data.every((x) => typeof x === "string")) {
      out = data;
    } else if (data && Array.isArray(data.tags)) {
      // { tags: [...] }
      return sanitizeTags(data.tags);
    } else if (Array.isArray(data) && data.length && typeof data[0] === "object") {
      // Array of objects -> pick one of common keys
      const key = ["tag", "name", "label", "value"].find((k) => k in data[0]) || "";
      if (key) out = (data as any[]).map((x) => String(x[key]));
    } else if (typeof data === "string") {
      // CSV / spaced / "glued" strings
      if (data.includes(",") || /\s/.test(data)) {
        out = tokenizeStringTags(data);
      } else {
        // "glued" case: attempt to detect by scanning allowed tokens
        const glued = data.toLowerCase();
        out = Array.from(ALLOWED_TAGS).filter(t => glued.includes(t));
      }
    }

    // Normalise, dedupe, and keep only allowed tags
    const filtered = Array.from(
      new Set(
        (out || [])
          .map((t) => t?.toString().toLowerCase().trim())
          .filter((t) => t && ALLOWED_TAGS.has(t))
      )
    );

    // Heuristic: if API returned "almost everything", warn and return empty to avoid spam
    const allowedCount = ALLOWED_TAGS.size;
    if (filtered.length >= Math.ceil(0.7 * allowedCount)) {
      setTagsWarning(
        "Tags endpoint may be returning the full ontology. Showing none until fixed."
      );
      return [];
    }

    return filtered;
  };

  // ---- Fetch tags for selected munro ----
  useEffect(() => {
    setTags(null);
    setTagsError(null);
    setTagsWarning(null);

    if (!selected) return;

    // If tags already present in the selected object, use them
    if (Array.isArray(selected.tags)) {
      setTags(sanitizeTags(selected.tags));
      return;
    }

    const endpoints = [
      `${API_BASE}/api/munros/${selected.id}/tags`,                     // preferred: ["ridge","scramble",...]
      `${API_BASE}/api/tags?munro_id=${encodeURIComponent(String(selected.id))}`, // alt
      `${API_BASE}/api/munros/${selected.id}`,                          // alt: { ..., tags:[...] }
    ];

    const fetchTags = async () => {
      setTagsLoading(true);
      try {
        for (const url of endpoints) {
          try {
            const { data } = await axios.get(url);
            const norm = sanitizeTags(data);
            if (norm.length || (Array.isArray(data?.tags) && data.tags.length)) {
              setTags(norm);
              return;
            }
          } catch {
            // try next
          }
        }
        throw new Error("No tag endpoint returned usable tags");
      } catch (e: any) {
        setTagsError("Couldn't load tags for this route.");
      } finally {
        setTagsLoading(false);
      }
    };

    fetchTags();
  }, [selected?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // IMPORTANT: hook expects Munro | null
  const gpxUrl = useSelectedGpxUrl(selected ?? null);

  return (
    <Box mt={6} position="relative">
      <Heading size="md" mb={4}>Explore a Munro</Heading>

      {/* Search Input */}
      <Box mb={4} maxW="520px" position="relative">
        <Input
          placeholder="Start typing a Munro name..."
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            if (!e.target.value) setSelected(null);
          }}
          onFocus={() => setShowDropdown(true)}
        />
        {showDropdown && options.length > 0 && (
          <Box
            border="1px solid #e2e8f0"
            borderTop="none"
            borderRadius="md"
            mt={-1}
            maxH="240px"
            overflowY="auto"
            position="absolute"
            bg="white"
            zIndex={10}
            width="100%"
            maxW="520px"
          >
            {options.map((m) => (
              <Box
                key={m.id}
                px={4}
                py={2}
                _hover={{ bg: "blue.50", cursor: "pointer" }}
                onClick={() => handleSelect(m)}
              >
                {m.name}
              </Box>
            ))}
          </Box>
        )}
      </Box>

      {selected && (
        <Box
          bg="white"
          border="1px solid"
          borderColor="gray.200"
          borderRadius="2xl"
          boxShadow="lg"
          overflow="hidden"
        >
          {/* Header */}
          <Box bg="blue.600" color="white" px={6} py={3}>
            <Heading size="lg" lineHeight="short">
              {selected.title || selected.name}
            </Heading>
            {selected.title && selected.name && selected.title !== selected.name && (
              <Text mt={1} color="blue.100" fontSize="sm">
                ⛰️ {selected.name}
              </Text>
            )}
          </Box>

          {/* Body */}
          <Box p={5}>
            {/* GPX errors */}
            {gpxError && (
              <Alert status="warning" mb={3}>
                <AlertIcon />
                {`Couldn't load GPX: ${gpxError}`}
              </Alert>
            )}

            {/* Map Preview — OpenTopoMap */}
            <Heading size="sm" mb={1}>Map Preview</Heading>
            <Box
              border="1px solid"
              borderColor="gray.200"
              rounded="lg"
              overflow="hidden"
              mb={5}
            >
              <MapContainer
                center={DEFAULT_CENTER}
                zoom={10}
                style={{ height: "360px", width: "100%" }}
              >
                <MapRefStash />
                <TileLayer
                  url="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png"
                  attribution='Map data: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, SRTM | Map style: &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (CC-BY-SA)'
                  maxZoom={17}
                />
                <GpxOverlay url={gpxUrl} onError={(msg) => setGpxError(msg)} />
              </MapContainer>
            </Box>

            {/* Quick facts */}
            <SimpleGrid columns={{ base: 1, md: 4 }} spacing={3} mb={5}>
              <Flex align="center" gap={2} bg="blue.50" p={2} rounded="md" border="1px solid" borderColor="blue.100">
                <span>🥾</span>
                <Text fontSize="sm"><strong>Distance:</strong> {selected.distance ?? "—"} km</Text>
              </Flex>
              <Flex align="center" gap={2} bg="green.50" p={2} rounded="md" border="1px solid" borderColor="green.100">
                <span>⏱️</span>
                <Text fontSize="sm"><strong>Time:</strong> {selected.time ?? "—"} hrs</Text>
              </Flex>
              <Flex align="center" gap={2} bg="purple.50" p={2} rounded="md" border="1px solid" borderColor="purple.100">
                <span>⛰️</span>
                <Text fontSize="sm"><strong>Grade:</strong> {selected.grade ?? "—"}</Text>
              </Flex>
              <Flex align="center" gap={2} bg="orange.50" p={2} rounded="md" border="1px solid" borderColor="orange.100">
                <span>🪵</span>
                <Text fontSize="sm"><strong>Bog:</strong> {selected.bog ?? "—"}/5</Text>
              </Flex>
            </SimpleGrid>

            {/* Overview */}
            {selected.summary && (
              <>
                <Heading size="sm" mb={1}>Overview</Heading>
                <Text fontSize="sm" mb={5} whiteSpace="pre-wrap" color="gray.700">
                  {selected.summary}
                </Text>
              </>
            )}

            {/* Keyword Tags — dynamic from DB with guardrails */}
            <Heading size="sm" mb={1}>Keyword Tags</Heading>
            <Box mb={6}>
              {tagsLoading && (
                <HStack>
                  <Spinner size="sm" />
                  <Text fontSize="sm" color="gray.600">Loading tags…</Text>
                </HStack>
              )}
              {!tagsLoading && (tagsError || tagsWarning) && (
                <Alert status={tagsError ? "error" : "warning"} rounded="md" mb={3}>
                  <AlertIcon />
                  {tagsError || tagsWarning}
                </Alert>
              )}
              {!tagsLoading && !tagsError && !tagsWarning && (
                <>
                  {tags && tags.length > 0 ? (
                    <Flex gap={2} wrap="wrap">
                      {tags.map((tag) => (
                        <CTag
                          key={tag}
                          size="sm"
                          variant="subtle"
                          colorScheme="blue"
                          border="1px solid"
                          borderColor="blue.200"
                          rounded="full"
                        >
                          <TagLabel>{tag}</TagLabel>
                        </CTag>
                      ))}
                    </Flex>
                  ) : (
                    <Text fontSize="sm" color="gray.600">No tags yet for this route.</Text>
                  )}
                </>
              )}
            </Box>

            {/* Terrain */}
            {selected.terrain && (
              <>
                <Heading size="sm" mb={1}>Terrain</Heading>
                <Box bg="gray.50" border="1px solid" borderColor="gray.200" p={3} rounded="lg" mb={5}>
                  <Flex align="flex-start" gap={3}>
                    <span>🧭</span>
                    <Text whiteSpace="pre-wrap" color="gray.800">{selected.terrain}</Text>
                  </Flex>
                </Box>
              </>
            )}

            {/* Public Transport */}
            {selected.public_transport && (
              <>
                <Heading size="sm" mb={1}>Public Transport</Heading>
                <Box bg="gray.50" border="1px solid" borderColor="gray.200" p={3} rounded="lg" mb={5}>
                  <Flex align="flex-start" gap={3}>
                    <span>🚌</span>
                    <Text whiteSpace="pre-wrap" color="gray.800">{selected.public_transport}</Text>
                  </Flex>
                </Box>
              </>
            )}

            {/* Start / Access */}
            {selected.start && (
              <>
                <Heading size="sm" mb={1}>Start / Access</Heading>
                <Box bg="gray.50" border="1px solid" borderColor="gray.200" p={3} rounded="lg" mb={5}>
                  <Flex align="flex-start" gap={3}>
                    <span>📍</span>
                    <Text whiteSpace="pre-wrap" color="gray.800">{selected.start}</Text>
                  </Flex>
                </Box>
              </>
            )}

            {/* Resources */}
            {(() => {
              const gpx = selected.gpx_file ? gpxUrl : undefined;
              return (gpx || selected?.url || selected?.route_url) ? (
                <>
                  <Heading size="sm" mb={1}>Resources</Heading>
                  <Flex gap={3} wrap="wrap" mb={5}>
                    {gpx && (
                      <Button size="sm" colorScheme="blue" variant="solid" onClick={() => openInNew(gpx)}>
                        📥 Download GPX
                      </Button>
                    )}
                    {selected?.url && (
                      <Button size="sm" variant="outline" onClick={() => openInNew(selected.url!)}>
                        🔗 Route URL
                      </Button>
                    )}
                    {selected?.route_url && !selected?.url && (
                      <Button size="sm" variant="outline" onClick={() => openInNew(selected.route_url!)}>
                        🔗 Route URL
                      </Button>
                    )}
                  </Flex>
                </>
              ) : null;
            })()}

            {/* Route Description */}
            {selected.description && (
              <>
                <Heading size="sm" mb={1}>Route Description</Heading>
                <Box bg="white" border="1px solid" borderColor="gray.200" p={4} rounded="lg">
                  <Text fontSize="sm" lineHeight="tall" whiteSpace="pre-wrap" color="gray.700">
                    {selected.description}
                  </Text>
                </Box>
              </>
            )}

            {/* Additional Details */}
            {(() => {
              const entries = Object.entries(selected).filter(
                ([k, v]) =>
                  !CORE_FIELDS.has(k) &&
                  v !== null &&
                  v !== undefined &&
                  String(v).trim() !== ""
              );
              if (!entries.length) return null;
              return (
                <>
                  <Heading size="sm" mt={6} mb={2}>Additional Details</Heading>
                  <SimpleGrid columns={{ base: 1, md: 2 }} spacing={3}>
                    {entries.map(([k, v]) => (
                      <Box key={k} p={3} border="1px solid" borderColor="gray.200" rounded="md" bg="white">
                        <Text fontSize="xs" color="gray.500">{prettyLabel(k)}</Text>
                        <Text fontWeight="medium" whiteSpace="pre-wrap">
                          {typeof v === "string" ? v : JSON.stringify(v)}
                        </Text>
                      </Box>
                    ))}
                  </SimpleGrid>
                </>
              );
            })()}
          </Box>
        </Box>
      )}
    </Box>
  );
}
