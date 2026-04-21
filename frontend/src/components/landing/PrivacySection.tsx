import AccordionItem from "./AccordionItem";
import SectionHeading from "./SectionHeading";
import SectionLabel from "./SectionLabel";
import SectionWrapper from "./SectionWrapper";

export default function PrivacySection() {
  return (
    <SectionWrapper id="privacy">
      <SectionLabel>Privacy & disclaimer</SectionLabel>
      <SectionHeading>
        What Spelix does with your video — and what it does not do.
      </SectionHeading>

      <div className="mt-12 grid items-start gap-10 md:grid-cols-12">
        <div className="md:col-span-8 md:col-start-3">
          <AccordionItem title="Your video is not kept." defaultOpen>
            <p>
              Raw video is deleted after processing. What Spelix retains is
              your skeleton data — joint coordinates and derived metrics — not
              your footage. You can view and download your data at any time
              from your profile, and you can delete your account completely
              whenever you want.
            </p>
          </AccordionItem>
          <AccordionItem title="Spelix is not a medical device.">
            <p>
              Spelix analyses movement patterns and grounds coaching in the
              published biomechanics literature. It is not a medical tool,
              and it is not a substitute for a physiotherapist, a qualified
              coach, or a medical professional. All feedback is for educational
              and performance purposes only.
            </p>
          </AccordionItem>
          <AccordionItem title="Your data belongs to you.">
            <p>
              Your analyses are yours. Spelix does not sell or share your data.
              Anonymised patterns may inform the Coach Brain's learning layer
              only after passing a minimum-group-size threshold that prevents
              any individual lifter from being identifiable.
            </p>
          </AccordionItem>
        </div>
      </div>
    </SectionWrapper>
  );
}
