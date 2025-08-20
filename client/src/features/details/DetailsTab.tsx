import "leaflet/dist/leaflet.css";
import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import {
  Box, Heading, Text, Input, Flex, SimpleGrid, Button,
  Alert, AlertIcon
} from "@chakra-ui/react";
import { MapContainer, TileLayer } from "react-leaflet";

import { Munro } from "../../types/munro";
import { prettyLabel } from "../../utils/labels";
import { useSelectedGpxUrl } from "../../hooks/useSelectedGpxUrl";
import { DEFAULT_CENTER } from "../../config/constants";
import MapRefStash from "../../components/map/MapRefStash";
import GpxOverlay from "../../components/map/GpxOverlay";

type Props = { initialMunro: Munro | null };

const API_BASE =
  (typeof process !== "undefined" && (process as any)?.env?.REACT_APP_API_BASE) ||
  "http://localhost:5000";

export default function DetailsTab({ initialMunro }: Props) {
  const [query, setQuery] = useState("");
  const [options, setOptions] = useState<Munro[]>([]);
  const [selected, setSelected] = useState<Munro | null>(null);
  const [showDropdown, setShowDropdown] = useState(false);
  const [gpxError, setGpxError] = useState<string | null>(null);

  // On mount:
  // 1) If initialMunro provided, use it
  // 2) Otherwise, default to "Ben Nevis"
  useEffect(() => {
    const init = async () => {
      if (initialMunro) {
        setSelected(initialMunro);
        setQuery(initialMunro.name);
        window.scrollTo({ top: 0, behavior: "smooth" });
        return;
      }
      try {
        const name = "Ben Nevis";
        const { data } = await axios.get<Munro[]>(
          `${API_BASE}/api/munros?search=${encodeURIComponent(name)}`
        );
        // Prefer exact match if present; fallback to first result
        const exact = (data || []).find(
          (m) => m.name?.toLowerCase().trim() === name.toLowerCase()
        );
        const choice = exact || (data?.length ? data[0] : null);
        if (choice) {
          setSelected(choice);
          setQuery(choice.name);
        }
      } catch (e) {
        // Swallow silently; user can still search manually
      }
    };
    init();
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
        const list = res.data as Munro[];
        const filtered = list.filter((m) =>
          m.name.toLowerCase().includes(query.toLowerCase())
        );
        setOptions(filtered);
        setShowDropdown(true);
      })
      .catch((err) => console.error(err));
  }, [query]);

  const handleSelect = (munro: Munro) => {
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
        "gpx_file","url","route_url"
      ]),
    []
  );

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
