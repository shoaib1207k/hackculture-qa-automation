import asyncio, sys
from hackathon_qa_automation.checks.factual.agents import compare_factual
from hackathon_qa_automation.common.logging_config import setup_logging
from hackathon_qa_automation.models import Check

def chk(desc): return Check(check_id="x", description=desc, type="factual", critical=True, crm_field="f")
PRICE, EMAIL, ADDR = chk("Introductory monthly plan price"), chk("Customer email address"), chk("Delivery address")
MODEM, RATE, PHONE = chk("Upfront cost of the modem"), chk("Peak electricity rate"), chk("Customer mobile number")
UNIT = "Unit 4, 18 Harbour View Drive, Parramatta NSW 2150"
CASES = [
 ("forty two dollars and ninety", "42.90 AUD", PRICE, "match"),
 ("forty five dollars and ninety", "42.90 AUD", PRICE, "mismatch"),
 ("seventy two dollars and ninety", "42.90 AUD", PRICE, "mismatch"),
 ("No extra cost", "0.00 AUD", MODEM, "match"),
 ("zero dollar upfront", "0.00 AUD", MODEM, "match"),
 ("$5 upfront", "0.00 AUD", MODEM, "mismatch"),
 ("sarah.mitchell@example.com", "sarah.mitchell@example.com", EMAIL, "match"),
 ("sarah dot mitchell at example dot com", "sarah.mitchell@example.com", EMAIL, "match"),
 ("j.smith@gmail.com", "j.smith@gmial.com", EMAIL, "mismatch"),
 ("sarah.mitchell@example.co", "sarah.mitchell@example.com", EMAIL, "mismatch"),
 ("18 Harbour View Dr, Parramatta NSW 2150", "18 Harbour View Drive, Parramatta NSW 2150", ADDR, "match"),
 ("18 Harbour View Drive, Parramatta NSW 2150", UNIT, ADDR, "mismatch"),
 ("Unit 4, 18 Harbour View Drive, Parramatta NSW 2151", UNIT, ADDR, "mismatch"),
 ("peak is 28.6 cents", "31.9c/kWh", RATE, "mismatch"),
 ("31.9 cents per kWh", "31.9c/kWh", RATE, "match"),
 ("oh four one two five five five seven eight three", "0412 555 783", PHONE, "match"),
 ("oh four one two five five five seven eight eight", "0412 555 783", PHONE, "mismatch"),
]
setup_logging()


async def main():
    outs = await asyncio.gather(*(compare_factual(s, c, k) for s, c, k, _ in CASES))
    bad = 0
    for (s, c, k, exp), o in zip(CASES, outs):
        ok = o.verdict == exp; bad += not ok
        print(f"{'ok ' if ok else 'BAD'} exp={exp:8} got={o.verdict:8} conf={o.confidence:.2f}  {s!r} vs {c!r}")
    print(f"\n{len(CASES)-bad}/{len(CASES)} as expected")
asyncio.run(main())
