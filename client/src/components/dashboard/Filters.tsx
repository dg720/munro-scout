import { Flex, Input, Select } from "@chakra-ui/react";

type SortOrder = "asc" | "desc";

type Props = {
  search: string;
  grade: string;
  bog: string;
  sortKey: string;
  sortOrder: SortOrder;
  onSearch: (v: string) => void;
  onGrade: (v: string) => void;
  onBog: (v: string) => void;
  onSortKey: (v: string) => void;
  onSortOrder: (v: SortOrder) => void;
};

export default function Filters({
  search, grade, bog, sortKey, sortOrder,
  onSearch, onGrade, onBog, onSortKey, onSortOrder
}: Props) {
  return (
    <Flex gap={4} wrap="wrap" mb={10}>
      <Input
        placeholder="Search by description..."
        value={search}
        onChange={(e) => onSearch(e.target.value)}
        w="full"
        maxW="250px"
      />
      <Select
        placeholder="Filter by grade"
        value={grade}
        onChange={(e) => onGrade(e.target.value)}
        maxW="180px"
      >
        {[1, 2, 3, 4, 5].map(g => <option key={g} value={g}>{g}</option>)}
      </Select>
      <Select
        placeholder="Max bog"
        value={bog}
        onChange={(e) => onBog(e.target.value)}
        maxW="180px"
      >
        {[1, 2, 3, 4, 5].map(b => <option key={b} value={b}>{b}</option>)}
      </Select>
      <Select
        placeholder="Sort by"
        value={sortKey}
        onChange={(e) => onSortKey(e.target.value)}
        maxW="180px"
      >
        <option value="name">Name (A–Z)</option>
        <option value="distance">Distance</option>
        <option value="time">Time</option>
      </Select>
      <Select
        placeholder="Order"
        value={sortOrder}
        onChange={(e) => onSortOrder(e.target.value as SortOrder)}
        maxW="140px"
      >
        <option value="asc">Asc</option>
        <option value="desc">Desc</option>
      </Select>
    </Flex>
  );
}
