/**
 * A break's detail and legs come from the API with the adjustment: the cause
 * and verdict from the investigation, both legs as MB Rec reports them.
 * These readers keep the components' existing call shape.
 */

export const breakDetail = (a) => a.detail;

export const breakLegs = (a) => a.legs;
