import "leaflet/dist/leaflet.css"; // required for proper map rendering
import "./config/leaflet";          // one-time Leaflet icon setup

import { MapContainer, TileLayer } from "react-leaflet";
import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import {
  Box, Container, Heading, Text, Input, Table, Thead, Tbody, Tr, Th, Td,
  TableContainer, Select, SimpleGrid, Stat, StatLabel, StatNumber, Flex,
  Divider, useDisclosure, Modal, ModalOverlay, ModalContent, ModalHeader,
  ModalCloseButton, ModalBody, ModalFooter, Button, Alert, AlertIcon
} from "@chakra-ui/react";
import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip as ChartTooltip, ResponsiveContainer
} from "recharts";

import { DEFAULT_CENTER } from "./config/constants";
import { prettyLabel } from "./utils/labels";
import { useSelectedGpxUrl } from "./hooks/useSelectedGpxUrl";
import MapRefStash from "./components/map/MapRefStash";
import GpxOverlay from "./components/map/GpxOverlay";
import { Munro } from "./types/munro";

// ==================== SMALL HELPERS (kept local for now) ===========

const CustomTooltip = ({ active, payload }: any) => {
  if (active && payload && payload.length) {
    return (
      <Box bg="white" border="1px solid #ccc" px={3} py={2} rounded="md" shadow="sm">
        <Text fontWeight="semibold">{payload[0].payload.name}</Text>
      </Box>
    );
  }
  return null;
};

// ==================== MAIN APP =====================================

export default function App() {
  const [munros, setMunros] = useState<Munro[]>([]);
  const [search, setSearch] = useState("");
  const [grade, setGrade] = useState("");
  const [bog, setBog] = useState("");
  const [sortKey, setSortKey] = useState("");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("asc");
  const [selectedMunro, setSelectedMunro] = useState<Munro | null>(null);
  const { isOpen, onOpen, onClose } = useDisclosure();
  const [activeTab, setActiveTab] = useState<"dashboard" | "chat" | "details">("dashboard");
  const [messages, setMessages] = useState<{ role: "user" | "assistant"; content: string }[]>([]);
  const [input, setInput] = useState("");

  useEffect(() => {
    const params = new URLSearchParams();
    if (search) params.append("search", search);
    if (grade) params.append("grade", grade);
    if (bog) params.append("bog", bog);
    axios
      .get(`http://localhost:5000/api/munros?${params.toString()}`)
      .then((res) => {
        let data = res.data as Munro[];
        if (sortKey) {
          data = [...data].sort((a, b) => {
            if (sortKey === "name") {
              const cmp = a.name.localeCompare(b.name, "en", { sensitivity: "base" });
              return sortOrder === "asc" ? cmp : -cmp;
            }
            const aVal = a[sortKey] as number;
            const bVal = b[sortKey] as number;
            return sortOrder === "asc" ? aVal - bVal : bVal - aVal;
          });
        }
        setMunros(data);
      })
      .catch((err) => console.error(err));
  }, [search, grade, bog, sortKey, sortOrder]);

  const stats = {
    total: munros.length,
    avgDistance: munros.reduce((sum, m) => sum + m.distance, 0) / (munros.length || 1),
    avgTime: munros.reduce((sum, m) => sum + m.time, 0) / (munros.length || 1),
    avgGrade: munros.reduce((sum, m) => sum + m.grade, 0) / (munros.length || 1),
    avgBog: munros.reduce((sum, m) => sum + m.bog, 0) / (munros.length || 1),
  };

  // ------- ChatTab (kept local for now) -------
  const ChatTab = () => (
    <Box mt={6}>
      <Heading size="md" mb={4}>Munro Scout Assistant</Heading>
      <Box bg="gray.50" p={4} rounded="lg" maxH="400px" overflowY="auto" mb={4} border="1px solid #e2e8f0">
        {messages.map((msg, idx) => (
          <Box key={idx} mb={3} textAlign={msg.role === "user" ? "right" : "left"}>
            <Text
              display="inline-block"
              bg={msg.role === "user" ? "blue.100" : "gray.200"}
              px={3} py={2} rounded="xl"
              maxW="80%"
            >
              {msg.content}
            </Text>
          </Box>
        ))}
      </Box>
      <Flex gap={2}>
        <Input
          placeholder="Ask about Munros..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && e.preventDefault()}
        />
        <Button onClick={() => {
          if (!input.trim()) return;
          setMessages([...messages, { role: "user", content: input }]);
          setInput("");
        }} colorScheme="blue">Send</Button>
      </Flex>
    </Box>
  );

  // ------- DetailsTab (still local; uses extracted mapping pieces) -------
  const DetailsTab = ({ initialMunro }: { initialMunro: Munro | null }) => {
    const [query, setQuery] = useState("");
    const [options, setOptions] = useState<Munro[]>([]);
    const [selected, setSelected] = useState<Munro | null>(null);
    const [showDropdown, setShowDropdown] = useState(false);
    const [gpxError, setGpxError] = useState<string | null>(null);

    useEffect(() => {
      if (initialMunro) {
        setSelected(initialMunro);
        setQuery(initialMunro.name);
        window.scrollTo({ top: 0, behavior: "smooth" });
      }
    }, [initialMunro]);

    useEffect(() => {
      if (!query.trim()) {
        setOptions([]);
        return;
      }
      axios
        .get(`http://localhost:5000/api/munros?search=${encodeURIComponent(query)}`)
        .then((res) => {
          const filtered = (res.data as Munro[]).filter((m: Munro) =>
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

    const CORE_FIELDS = new Set([
      "id","name","summary","distance","time","grade","bog","start",
      "title","terrain","public_transport","description",
      "gpx_file","url","route_url"
    ]);

    const gpxUrl = useSelectedGpxUrl(selected);

    return (
      <Box mt={6} position="relative">
        <Heading size="md" mb={4}>Explore a Munro</Heading>

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

            <Box p={5}>
              {gpxError && (
                <Alert status="warning" mb={3}>
                  <AlertIcon />
                  {`Couldn't load GPX: ${gpxError}`}
                </Alert>
              )}

              <Heading size="sm" mb={1}>Map Preview</Heading>
              <Box border="1px solid" borderColor="gray.200" rounded="lg" overflow="hidden" mb={5}>
                <MapContainer center={DEFAULT_CENTER} zoom={10} style={{ height: "360px", width: "100%" }}>
                  <MapRefStash />
                  <TileLayer
                    url="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png"
                    attribution='Map data: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, SRTM | Map style: &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (CC-BY-SA)'
                    maxZoom={17}
                  />
                  <GpxOverlay url={gpxUrl} onError={(msg) => setGpxError(msg)} />
                </MapContainer>
              </Box>

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

              {selected.summary && (
                <>
                  <Heading size="sm" mb={1}>Overview</Heading>
                  <Text fontSize="sm" mb={5} whiteSpace="pre-wrap" color="gray.700">
                    {selected.summary}
                  </Text>
                </>
              )}

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

              <Heading size="sm" mb={1}>Keyword Tags</Heading>
              <Flex gap={2} wrap="wrap" mb={6}>
                {["scrambling","rocky","challenging","exposed","flat","ridge","quiet","family-friendly"].map(tag => (
                  <Box
                    key={tag}
                    px={3}
                    py={1}
                    bg="blue.50"
                    border="1px solid"
                    borderColor="blue.200"
                    rounded="full"
                    fontSize="xs"
                    color="blue.800"
                  >
                    {tag}
                  </Box>
                ))}
              </Flex>

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

              {(() => {
                const entries = Object.entries(selected).filter(
                  ([k, v]) => !CORE_FIELDS.has(k) && v !== null && v !== undefined && String(v).trim() !== ""
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
  };

  return (
    <Box minH="100vh" bgGradient="linear(to-br, gray.50, white)">
      <Box bg="blue.700" color="white" py={6} px={6} shadow="md">
        <Heading size="lg">Munro Explorer Dashboard</Heading>
        <Text mt={2} fontSize="sm" color="blue.100">
          Discover and analyze Munro mountains in Scotland based on distance, difficulty, and more.
        </Text>
        <Flex mt={4} gap={4}>
          <Button variant={activeTab === "dashboard" ? "solid" : "outline"} onClick={() => setActiveTab("dashboard")} colorScheme="whiteAlpha">Dashboard</Button>
          <Button variant={activeTab === "chat" ? "solid" : "outline"} onClick={() => setActiveTab("chat")} colorScheme="whiteAlpha">Chat Assistant</Button>
          <Button variant={activeTab === "details" ? "solid" : "outline"} onClick={() => setActiveTab("details")} colorScheme="whiteAlpha">Munro Details</Button>
        </Flex>
      </Box>

      <Container maxW="6xl" py={10}>
        {activeTab === "dashboard" ? (
          <>
            <Heading size="md" mb={2}>Overview Statistics</Heading>
            <Divider mb={6} />
            <SimpleGrid columns={{ base: 2, md: 5 }} spacing={4} mb={10}>
              <Stat><StatLabel>Total Munros</StatLabel><StatNumber>{stats.total}</StatNumber></Stat>
              <Stat><StatLabel>Avg Distance</StatLabel><StatNumber>{stats.avgDistance.toFixed(1)}</StatNumber></Stat>
              <Stat><StatLabel>Avg Time</StatLabel><StatNumber>{stats.avgTime.toFixed(1)}</StatNumber></Stat>
              <Stat><StatLabel>Avg Grade</StatLabel><StatNumber>{stats.avgGrade.toFixed(1)}</StatNumber></Stat>
              <Stat><StatLabel>Avg Bog</StatLabel><StatNumber>{stats.avgBog.toFixed(1)}</StatNumber></Stat>
            </SimpleGrid>

            <Heading size="md" mb={2}>Distance vs Time</Heading>
            <Divider mb={6} />
            <Box h="300px" mb={10}>
              <ResponsiveContainer>
                <ScatterChart margin={{ top: 10, right: 30, bottom: 10, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis type="number" dataKey="distance" name="Distance (km)" domain={[5, 40]} label={{ value: "Distance (km)", position: "insideBottomRight", offset: -5 }} />
                  <YAxis type="number" dataKey="time" name="Time (hrs)" label={{ value: "Time (hrs)", angle: -90, position: "insideLeft" }} />
                  <ChartTooltip content={<CustomTooltip />} cursor={{ strokeDasharray: "3 3" }} />
                  <Scatter name="Munros" data={munros} fill="#3182ce" isAnimationActive={false} />
                </ScatterChart>
              </ResponsiveContainer>
            </Box>

            <Heading size="md" mb={2}>Filters & Sorting</Heading>
            <Divider mb={4} />
            <Flex gap={4} wrap="wrap" mb={10}>
              <Input placeholder="Search by name..." value={search} onChange={(e) => setSearch(e.target.value)} w="full" maxW="250px" />
              <Select placeholder="Filter by grade" value={grade} onChange={(e) => setGrade(e.target.value)} maxW="180px">
                {[1, 2, 3, 4, 5].map(g => <option key={g} value={g}>{g}</option>)}
              </Select>
              <Select placeholder="Max bog" value={bog} onChange={(e) => setBog(e.target.value)} maxW="180px">
                {[1, 2, 3, 4, 5].map(b => <option key={b} value={b}>{b}</option>)}
              </Select>
              <Select placeholder="Sort by" value={sortKey} onChange={(e) => setSortKey(e.target.value)} maxW="180px">
                <option value="name">Name (A–Z)</option>
                <option value="distance">Distance</option>
                <option value="time">Time</option>
              </Select>
              <Select placeholder="Order" value={sortOrder} onChange={(e) => setSortOrder(e.target.value as "asc" | "desc")} maxW="140px">
                <option value="asc">Asc</option>
                <option value="desc">Desc</option>
              </Select>
            </Flex>

            <Heading size="md" mb={2}>Munro List</Heading>
            <Divider mb={4} />
            <Box bg="white" border="1px solid" borderColor="blue.100" shadow="lg" rounded="2xl" overflow="hidden">
              <TableContainer maxH="500px" overflowY="auto">
                <Table size="sm" variant="simple">
                  <Thead position="sticky" top={0} bg="blue.500" color="white" zIndex={1}>
                    <Tr>
                      <Th color="white">Name</Th>
                      <Th textAlign="center" color="white">Distance (km)</Th>
                      <Th textAlign="center" color="white">Time (hrs)</Th>
                      <Th textAlign="center" color="white">Grade</Th>
                      <Th textAlign="center" color="white">Bog</Th>
                    </Tr>
                  </Thead>
                  <Tbody>
                    {munros.map((m) => (
                      <Tr
                        key={m.id}
                        _hover={{ bg: "blue.50" }}
                        cursor="pointer"
                        onClick={() => { setSelectedMunro(m); onOpen(); }}
                      >
                        <Td fontWeight="semibold">{m.name}</Td>
                        <Td textAlign="center">{m.distance}</Td>
                        <Td textAlign="center">{m.time}</Td>
                        <Td textAlign="center">{m.grade}</Td>
                        <Td textAlign="center">{m.bog}</Td>
                      </Tr>
                    ))}
                  </Tbody>
                </Table>
              </TableContainer>
            </Box>
          </>
        ) : activeTab === "chat" ? (
          <ChatTab />
        ) : (
          <DetailsTab initialMunro={selectedMunro} />
        )}
        <Text mt={12} textAlign="center" fontSize="sm" color="gray.400">
          Built with Flask, React & Chakra UI — demo project by Dhruv
        </Text>

        <Modal isOpen={isOpen} onClose={onClose} size="lg">
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>{selectedMunro?.title || selectedMunro?.name}</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <Text mb={4} fontSize="sm" whiteSpace="pre-wrap">{selectedMunro?.summary}</Text>
              <SimpleGrid columns={2} spacing={4}>
                <Flex align="center" gap={3}><Text><strong>Distance:</strong> {selectedMunro?.distance} km</Text></Flex>
                <Flex align="center" gap={3}><Text><strong>Time:</strong> {selectedMunro?.time} hrs</Text></Flex>
                <Flex align="center" gap={3}><Text><strong>Grade:</strong> {selectedMunro?.grade}</Text></Flex>
                <Flex align="center" gap={3}><Text><strong>Bog:</strong> {selectedMunro?.bog}/5</Text></Flex>
                <Flex align="center" gap={3} gridColumn="span 2"><Text><strong>Start Point:</strong> {selectedMunro?.start}</Text></Flex>
              </SimpleGrid>
            </ModalBody>
            <ModalFooter>
              <Flex gap={3}>
                <Button variant="ghost" onClick={onClose}>Close</Button>
                <Button colorScheme="blue" onClick={() => { setActiveTab("details"); onClose(); }}>
                  View in Details Tab
                </Button>
              </Flex>
            </ModalFooter>
          </ModalContent>
        </Modal>
      </Container>
    </Box>
  );
}
