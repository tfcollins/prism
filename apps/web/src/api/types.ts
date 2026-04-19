export interface User {
  id: string;
  email: string;
}

export interface Project {
  id: string;
  slug: string;
  name: string;
  description: string;
}

export interface CreateProjectRequest {
  slug: string;
  name: string;
  description?: string;
}
