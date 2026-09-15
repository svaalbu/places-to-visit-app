export type GeoHit = {
  name: string;
  address: string;
  latitude: number;
  longitude: number;
};

export async function searchOsloPlaces(query: string): Promise<GeoHit[]> {
  const trimmed = query.trim();
  if (trimmed.length < 2) {
    return [];
  }

  const url = new URL('https://nominatim.openstreetmap.org/search');
  url.searchParams.set('format', 'jsonv2');
  url.searchParams.set('q', `${trimmed}, Oslo, Norway`);
  url.searchParams.set('addressdetails', '1');
  url.searchParams.set('limit', '6');
  url.searchParams.set('countrycodes', 'no');

  const response = await fetch(url.toString(), {
    headers: {
      Accept: 'application/json',
      'User-Agent': 'Bordbok/1.0 (personal restaurant notebook)',
    },
  });

  if (!response.ok) {
    throw new Error('Could not search Oslo right now.');
  }

  const rows = (await response.json()) as Array<{
    display_name: string;
    lat: string;
    lon: string;
    name?: string;
    address?: {
      road?: string;
      house_number?: string;
      suburb?: string;
      neighbourhood?: string;
      city_district?: string;
    };
  }>;

  return rows.map((row) => {
    const road = [row.address?.road, row.address?.house_number].filter(Boolean).join(' ');
    return {
      name: row.name || trimmed,
      address: road || row.display_name.split(',')[0] || trimmed,
      latitude: Number(row.lat),
      longitude: Number(row.lon),
    };
  });
}
