import { PrismaClient } from "@prisma/client";
import { PrismaPg } from "@prisma/adapter-pg";
import bcrypt from "bcryptjs";

const adapter = new PrismaPg({ connectionString: process.env.DATABASE_URL! });
const prisma = new PrismaClient({ adapter });

async function main() {
  const hash = await bcrypt.hash("admin1234", 10);
  await prisma.doctor.upsert({
    where: { username: "doctor1" },
    update: {},
    create: {
      username: "doctor1",
      passwordHash: hash,
      name: "김정형",
      hospital: "달려라병원",
    },
  });
  console.log("Seeded doctor: doctor1 / admin1234");
}

main().catch(console.error).finally(() => prisma.$disconnect());
