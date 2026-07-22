export interface Clinic {
  name: string;
  address: string;
  rating?: number | string | null;
  place_id: string;
}

export interface MessageMetadata {
  clinics?: Clinic[];
  [key: string]: any;
}

export interface Message {
  role: "user" | "assistant";
  content: string;
  metadata?: MessageMetadata;
}
